from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_g3_gate_contract_is_explicit() -> None:
    gate = (ROOT / "docs/03-deliverables/G3-demand-plan-taquilla-routing/README.md").read_text(
        encoding="utf-8"
    )
    demand = (ROOT / "src/modules/demand/README.md").read_text(encoding="utf-8")

    assert "G3.1 — Production Plan & Taquilla Foundation" in gate
    assert "Stable UUIDs are canonical identities" in gate
    assert "A Plan may contain multiple Taquillas" in gate
    assert "A Taquilla may contain multiple product Articles" in gate
    assert "G4 APS" in gate
    assert "G5 MES" in gate

    assert "Production Plan" in demand
    assert "Taquilla" in demand
    assert "G2 remains owner" in demand
    assert "G4 APS owns finite-capacity sequencing" in demand
    assert "G5 MES owns actual execution" in demand
