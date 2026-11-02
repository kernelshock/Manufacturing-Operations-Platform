from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_5_publication_is_immutable_versioned_and_replan_only() -> None:
    lifecycle = _read("src/mop/aps/lifecycle_models.py")
    service = _read("src/mop/aps/service.py")
    migration = _read("migrations/versions/0023_g4_5_schedule_lifecycle.py")

    for required in (
        "SchedulePublication",
        "PublishedScheduledOperation",
        "PublishedScheduledOperationSegment",
        "SUPERSEDED",
        "supersedes_publication_id",
        "schedule_fingerprint",
        "replan_from_run_id",
        "replan_reason",
        "compare_replan_to_published",
        "published scheduling run cannot be cancelled",
    ):
        assert required in lifecycle or required in service or required in migration

    assert "uq_aps_publication_current_scenario" in lifecycle
    assert "ck_aps_run_replan_provenance" in migration

    for forbidden in (
        "actual_start",
        "actual_finish",
        "scrap_quantity",
        "operator_id",
    ):
        assert forbidden not in lifecycle
