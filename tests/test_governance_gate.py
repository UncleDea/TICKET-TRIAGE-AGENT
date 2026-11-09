"""CI test: the release is blocked unless the evaluation gate passes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "governance" / "eval"))
import run_eval  # noqa: E402


def test_governance_gate_passes():
    report = run_eval.evaluate()
    assert report["gate"] == "PASS", "Governance gate failed: " + "; ".join(report["failures"])
