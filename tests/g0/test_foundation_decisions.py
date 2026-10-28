from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs/00-governance/decisions/DECISION-REGISTER.md"

def test_foundation_decisions_are_resolved_or_deferred():
    text = REGISTER.read_text(encoding="utf-8")
    required = {
        "DEC-007": "ACCEPTED",
        "DEC-008": "ACCEPTED",
        "DEC-009": "ACCEPTED",
        "DEC-018": "ACCEPTED",
        "DEC-019": "ACCEPTED",
        "DEC-020": "ACCEPTED",
        "DEC-021": "DEFERRED",
    }
    for decision_id, status in required.items():
        rows = [line for line in text.splitlines() if f"| {decision_id} |" in line]
        assert len(rows) == 1, f"Expected exactly one row for {decision_id}"
        assert f"| {status} |" in rows[0], f"{decision_id} must be {status}: {rows[0]}"
