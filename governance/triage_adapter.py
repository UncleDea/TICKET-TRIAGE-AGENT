"""Adapter between the governance tests and TICKET-TRIAGE-AGENT.

The governance tests only ever call classify(ticket_text). This adapter sends the
text through YOUR real pipeline:

    triage_agent.run_triage()          -> real validation, confidence threshold, fallback
    supervisor.routing.choose_next_node -> your real human-approval (HITL) rule

and returns:
    {"critical": bool, "severity": str, "needs_human": bool}

Which model is used:
  * OPENAI_API_KEY is set  -> your real ChatOpenAI model (from triage_agent/config.py)
  * OPENAI_API_KEY not set -> a keyword stand-in model, so the kit still runs in
                              GitHub Actions with no key and no cost. Only the LLM
                              is swapped; everything else is your real code.
  * Force one or the other with TRIAGE_EVAL_MODEL=real or TRIAGE_EVAL_MODEL=fake
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from triage_agent.agent import run_triage  # noqa: E402
from triage_agent.schemas import TriageClassification  # noqa: E402
from supervisor.routing import choose_next_node  # noqa: E402

# Severities that count as "flagged urgent" for the governance metric.
# Both route to a human under your Supervisor policy. Tighten to {"critical"}
# if the committee decides only "critical" counts.
URGENT_SEVERITIES = {"high", "critical"}


# ---------------------------------------------------------------- stand-in model
CRITICAL_KEYWORDS = [
    "ransomware", "outage", "down", "breach", "locked out", "malware",
    "compromised", "offline", "crashed", "corrupted", "phishing",
]


class _KeywordStructured:
    def invoke(self, messages):
        text = str(messages[-1][1] if isinstance(messages[-1], tuple) else messages[-1]).lower()
        urgent = any(k in text for k in CRITICAL_KEYWORDS)
        return TriageClassification(
            category="technical" if urgent else "other",
            severity="critical" if urgent else "low",
            confidence=0.95,
            reasoning="keyword stand-in model (no API key)",
        )


class KeywordModel:
    """Mimics ChatOpenAI.with_structured_output(...).invoke(...) without an API call."""

    def with_structured_output(self, _schema):
        return _KeywordStructured()


def _pick_model():
    mode = os.environ.get("TRIAGE_EVAL_MODEL", "").lower()
    if mode == "fake" or (mode != "real" and not os.environ.get("OPENAI_API_KEY")):
        return KeywordModel()
    return None  # None = run_triage builds your real ChatOpenAI model


# ---------------------------------------------------------------- the adapter
def classify(ticket_text: str) -> dict:
    ticket = {
        "ticket_id": "EVAL",
        "raw_text": ticket_text,
        "customer_id": None,
        "channel": "email",
        "received_at": datetime.now(timezone.utc),
    }
    with contextlib.redirect_stdout(io.StringIO()):  # hide run_triage's per-ticket log lines
        state = run_triage(ticket, model=_pick_model())
    return {
        "critical": state.severity in URGENT_SEVERITIES,
        "severity": state.severity,
        "needs_human": choose_next_node(state) == "hitl",
    }
