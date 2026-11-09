# AI Governance Kit for TICKET-TRIAGE-AGENT

Copy these folders into the root of your TICKET-TRIAGE-AGENT repository:

    governance/                     governance card, adapter, evaluation harness, golden dataset
    tests/test_governance_gate.py   CI test: blocks release if the evaluation gate fails
    tests/test_prompt_injection.py  red-team tests for prompt injection
    .github/workflows/governance-gate.yml   GitHub Actions workflow

Then:
1. python governance/eval/run_eval.py      (runs on the keyword baseline first: expect GATE: BLOCK)
2. pytest -q                               (11 injection tests pass on the baseline; the gate test fails until you fix the gap)
3. Edit governance/triage_adapter.py so classify() calls your real agent, and run both again.

All ticket data is synthetic. Never commit real client tickets.
Lab instructions: LAB-AIG-07, 08 and 09 in the AI Governance Bootcamp (MSP Edition).
