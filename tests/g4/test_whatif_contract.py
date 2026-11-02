from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_7_whatif_is_isolated_and_explicitly_applied() -> None:
    models = _read("src/mop/aps/whatif_models.py")
    service = _read("src/mop/aps/service.py")
    api = _read("src/mop/api/v1/aps_whatif.py")

    for required in (
        "WhatIfScenario",
        "WhatIfException",
        "RESOURCE_BLACKOUT",
        "RESOURCE_CAPACITY_FACTOR",
        "baseline_publication_id",
        "candidate_run_id",
        'status="CAPACITY_PROJECTED"',
        "solve_finite_capacity",
        "compare_replan_to_published",
        "apply_whatif",
        "discard_whatif",
        'require_global_permission("aps.edit")',
    ):
        assert required in models or required in service or required in api

    assert "what-if baseline must be the CURRENT publication" in service
    assert "what-if baseline is no longer CURRENT" in service

    for forbidden in (
        "RoutingRevision.status =",
        "TaquillaProductLine.requested_quantity =",
        "ManufacturingCalendar.status =",
        "Resource.active =",
    ):
        assert forbidden not in service
