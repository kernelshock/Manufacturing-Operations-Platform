from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_gate_hardening_invariants() -> None:
    readme = _read("docs/03-deliverables/G4-aps/README.md")
    service = _read("src/mop/aps/service.py")
    expansion_api = _read("src/mop/api/v1/aps_expansion.py")
    capacity_api = _read("src/mop/api/v1/aps_capacity.py")
    schedule_api = _read("src/mop/api/v1/aps_schedule.py")
    lifecycle_api = _read("src/mop/api/v1/aps_lifecycle.py")
    gantt_api = _read("src/mop/api/v1/aps_gantt.py")
    whatif_api = _read("src/mop/api/v1/aps_whatif.py")
    lifecycle_models = _read("src/mop/aps/lifecycle_models.py")
    whatif_models = _read("src/mop/aps/whatif_models.py")
    gantt_frontend = _read("frontend/src/shell/GanttPanel.tsx")
    whatif_frontend = _read("frontend/src/shell/WhatIfPanel.tsx")

    for slice_name in (
        "G4.1",
        "G4.2",
        "G4.3",
        "G4.4",
        "G4.5",
        "G4.6",
        "G4.7",
    ):
        assert f"{slice_name} —" in readme
        assert "COMPLETED" in readme[readme.index(f"{slice_name} —"):readme.index(f"{slice_name} —") + 220]

    for required_rule in (
        "planned timestamps belong to APS only",
        "actual timestamps remain MES-owned",
        "what-if scenario cannot silently replace the published schedule",
        "Published schedules are immutable snapshots",
        "Missing or ambiguous planning inputs produce blockers",
    ):
        assert required_rule.lower() in readme.lower()

    mutation_contracts = {
        expansion_api: ("aps.run.materialize",),
        capacity_api: ("aps.run.capacity.project",),
        schedule_api: ("aps.run.solve",),
        lifecycle_api: ("aps.run.replan.create", "aps.schedule.publish"),
        whatif_api: (
            "aps.whatif.create",
            "aps.whatif.exception.add",
            "aps.whatif.evaluate",
            "aps.whatif.apply",
            "aps.whatif.discard",
        ),
    }
    for source, audit_actions in mutation_contracts.items():
        assert 'require_global_permission("aps.edit")' in source
        for action in audit_actions:
            assert f'action="{action}"' in source

    assert 'require_global_permission("aps.read")' in gantt_api
    assert "@router.post" not in gantt_api
    assert "solve_finite_capacity" not in gantt_api
    assert "publish_schedule" not in gantt_api

    assert 'status IN (\'CURRENT\', \'SUPERSEDED\')' in lifecycle_models
    assert "uq_aps_publication_current_scenario" in lifecycle_models
    assert "schedule_fingerprint" in lifecycle_models

    assert "RESOURCE_BLACKOUT" in whatif_models
    assert "RESOURCE_CAPACITY_FACTOR" in whatif_models
    assert "baseline_publication_id" in whatif_models
    assert "candidate_run_id" in whatif_models

    for forbidden in (
        "actual_start",
        "actual_finish",
        "produced_quantity_actual",
        "scrap_quantity",
        "operator_id",
    ):
        assert forbidden not in lifecycle_models
        assert forbidden not in whatif_models

    assert "operations = sorted(" in service
    assert "taquillas[item.taquilla_id].sequence_no" in service
    assert "item.product_sequence_no" in service
    assert "item.routing_sequence_no" in service
    assert "alternatives.sort(key=lambda item: (item[0], item[1], item[2], item[3]))" in service

    for replay_guard in (
        'if run.status == "EXPANDED"',
        'if run.status == "CAPACITY_PROJECTED"',
        'if run.status == "SCHEDULED"',
        "if existing is not None:",
    ):
        assert replay_guard in service

    assert "PublishedScheduledOperation" in service
    assert "PublishedScheduledOperationSegment" in service
    assert "what-if baseline is no longer CURRENT" in service
    assert "session.flush()" in service

    assert "frontend no replanifica" in gantt_frontend.lower()
    assert "baseline current intacto hasta aplicar" in whatif_frontend.lower()


def test_g4_scope_excludes_later_gate_authority() -> None:
    aps_files = [
        _read("src/mop/aps/models.py"),
        _read("src/mop/aps/operation_models.py"),
        _read("src/mop/aps/capacity_models.py"),
        _read("src/mop/aps/schedule_models.py"),
        _read("src/mop/aps/lifecycle_models.py"),
        _read("src/mop/aps/whatif_models.py"),
    ]
    combined = "\n".join(aps_files).lower()

    for forbidden_authority in (
        "inventory_balance",
        "purchase_order",
        "maintenance_work_order",
        "technician_id",
        "employee_skill",
        "actual_start",
        "actual_finish",
        "scrap_quantity",
    ):
        assert forbidden_authority not in combined
