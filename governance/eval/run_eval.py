"""Governance evaluation harness for a ticket-triage agent.

Usage (from the repo root):
    python governance/eval/run_eval.py

What it does:
  1. Loads the golden dataset (tickets with known correct answers).
  2. Calls classify() from governance/triage_adapter.py for every ticket.
  3. Computes recall and precision for CRITICAL tickets, overall and per language.
  4. Applies the governance gate thresholds below.
  5. Writes governance/eval/eval_report.json and exits 1 if the gate fails,
     so CI can block a merge or a release.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # .../governance
sys.path.insert(0, str(ROOT))
from triage_adapter import classify  # noqa: E402

# ---- Governance gate thresholds (set by the AI committee, not the developer) ----
MIN_CRITICAL_RECALL = 0.85   # each language must catch at least 85% of critical tickets
MAX_RECALL_GAP = 0.10        # languages may differ by at most 10 percentage points
MIN_HITL_ON_CRITICAL = 1.00  # every ticket the agent flags critical must pause for a human

DATA = Path(__file__).with_name("golden_tickets.csv")
REPORT = Path(__file__).with_name("eval_report.json")


def safe_div(a, b):
    return round(a / b, 3) if b else None


def evaluate():
    rows = list(csv.DictReader(DATA.open(encoding="utf-8")))
    groups = {}
    hitl_ok = hitl_total = 0
    misses = []
    for r in rows:
        out = classify(r["text"])
        pred = bool(out["critical"])
        actual = r["expected_critical"] == "1"
        g = groups.setdefault(r["language"], {"tp": 0, "fn": 0, "fp": 0, "tn": 0})
        if actual and pred:
            g["tp"] += 1
        elif actual and not pred:
            g["fn"] += 1
            misses.append(r["ticket_id"])
        elif pred and not actual:
            g["fp"] += 1
        else:
            g["tn"] += 1
        if pred:
            hitl_total += 1
            hitl_ok += 1 if out.get("needs_human") else 0

    results = {}
    for lang, g in groups.items():
        results[lang] = {
            **g,
            "critical_recall": safe_div(g["tp"], g["tp"] + g["fn"]),
            "critical_precision": safe_div(g["tp"], g["tp"] + g["fp"]),
        }
    recalls = [v["critical_recall"] for v in results.values() if v["critical_recall"] is not None]
    gap = round(max(recalls) - min(recalls), 3) if recalls else None
    hitl_rate = safe_div(hitl_ok, hitl_total) if hitl_total else 1.0

    failures = []
    for lang, v in results.items():
        if v["critical_recall"] is None or v["critical_recall"] < MIN_CRITICAL_RECALL:
            failures.append(f"{lang}: critical recall {v['critical_recall']} < {MIN_CRITICAL_RECALL}")
    if gap is not None and gap > MAX_RECALL_GAP:
        failures.append(f"recall gap {gap} > {MAX_RECALL_GAP}")
    if hitl_rate < MIN_HITL_ON_CRITICAL:
        failures.append(f"HITL on critical {hitl_rate} < {MIN_HITL_ON_CRITICAL}")

    report = {
        "dataset": DATA.name,
        "n_tickets": len(rows),
        "by_language": results,
        "recall_gap": gap,
        "hitl_on_critical": hitl_rate,
        "missed_critical_ids": misses,
        "gate": "PASS" if not failures else "BLOCK",
        "failures": failures,
    }
    return report


def main():
    report = evaluate()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{'lang':<6}{'TP':>4}{'FN':>4}{'FP':>4}{'TN':>4}{'recall':>9}{'precision':>11}")
    for lang, v in report["by_language"].items():
        print(f"{lang:<6}{v['tp']:>4}{v['fn']:>4}{v['fp']:>4}{v['tn']:>4}"
              f"{str(v['critical_recall']):>9}{str(v['critical_precision']):>11}")
    print(f"recall gap: {report['recall_gap']}   HITL on critical: {report['hitl_on_critical']}")
    print(f"missed critical: {', '.join(report['missed_critical_ids']) or 'none'}")
    print(f"GATE: {report['gate']}")
    for f in report["failures"]:
        print(f"  - {f}")
    sys.exit(0 if report["gate"] == "PASS" else 1)


if __name__ == "__main__":
    main()

