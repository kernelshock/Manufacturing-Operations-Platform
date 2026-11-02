from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g3_exit_criteria_and_slice_completion_are_recorded() -> None:
    gate = _read("docs/03-deliverables/G3-demand-plan-taquilla-routing/README.md")

    for slice_id in (
        "G3.1",
        "G3.2",
        "G3.3",
        "G3.4",
        "G3.5",
        "G3.6",
        "G3.7",
    ):
        assert f"{slice_id} —" in gate
        assert "COMPLETED" in gate[gate.index(f"{slice_id} —"):][:220]

    for criterion in (
        "Stable UUIDs are canonical identities",
        "A Plan may contain multiple Taquillas",
        "A Taquilla may contain multiple product Articles",
        "Double-deck information is explicit data",
        "Imported/legacy records retain source provenance and are idempotent",
        "G3 records demand intent and administrative state",
    ):
        assert criterion in gate


def test_g3_domain_has_no_aps_or_mes_owned_state() -> None:
    domain = "\n".join(
        _read(path)
        for path in (
            "src/mop/demand/models.py",
            "src/mop/demand/schemas.py",
            "src/mop/demand/service.py",
            "src/mop/api/v1/demand.py",
        )
    )

    forbidden_owned_state = (
        "planned_start",
        "planned_finish",
        "planned_end",
        "finite_capacity",
        "actual_start",
        "actual_finish",
        "actual_end",
        "produced_quantity",
        "scrap_quantity",
    )
    for forbidden in forbidden_owned_state:
        assert forbidden not in domain


def test_g3_api_requires_demand_permissions_and_audits_mutations() -> None:
    api = _read("src/mop/api/v1/demand.py")

    assert 'require_global_permission("demand.read")' in api
    assert 'require_global_permission("demand.edit")' in api

    required_audit_actions = (
        "demand.plan.create",
        "demand.plan.number.update",
        "demand.plan.status.transition",
        "demand.taquilla.create",
        "demand.taquilla.topology.update",
        "demand.taquilla.status.transition",
        "demand.taquilla_product.create",
        "demand.taquilla_product.update",
        "demand.taquilla_product.routing.resolve",
        "demand.taquilla_product.routing.override",
        "demand.plan.historical_completion",
        "demand.taquilla.cancel",
        "demand.plan.cancel",
        "demand.taquilla.delete_draft",
        "demand.taquilla.assimilation.import",
    )
    for action in required_audit_actions:
        assert f'action="{action}"' in api


def test_g3_assimilation_contract_preserves_explicit_source_semantics() -> None:
    schemas = _read("src/mop/demand/schemas.py")
    service = _read("src/mop/demand/service.py")

    for field in (
        "source_document_key",
        "source_line_key",
        "payload_fingerprint",
        "parser_version",
        "mapping_version",
        "deck_position",
    ):
        assert field in schemas or field in service

    assert "DOUBLE_DECK assimilation must represent both UPPER and LOWER" in schemas
    assert "SIMPLE assimilation requires SINGLE on every line" in schemas
    assert "idempotent_replay=True" in service


def test_g3_frontend_is_permission_driven_and_does_not_claim_aps_ownership() -> None:
    permissions = _read("frontend/src/lib/permissions.ts")
    panel = _read("frontend/src/shell/DemandPanel.tsx")

    assert '"demand.read"' in permissions
    assert '"demand.edit"' in permissions
    assert "Planificación / Taquillas" in permissions
    assert "Gantt" in panel
    assert "capacidad finita" in panel
    assert "No contiene secuenciación" in panel
