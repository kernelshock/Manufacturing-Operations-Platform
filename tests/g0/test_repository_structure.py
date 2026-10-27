from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "docs/00-governance/roadmap/ROADMAP.md",
    "docs/00-governance/worklog/WORKLOG.csv",
    "docs/00-governance/decisions/DECISION-REGISTER.md",
    "docs/01-architecture/ADR/ADR-0001-modular-monolith.md",
    "docs/01-architecture/ADR/ADR-0002-api-first-event-oriented.md",
    "docs/01-architecture/domain-model/CANONICAL-DOMAIN-MODEL.md",
    "docs/01-architecture/event-catalog/EVENT-CATALOG.md",
    "docs/01-architecture/modules/MODULE-MAP.md",
    "docs/01-architecture/system-of-record/SYSTEM-OF-RECORD.md",
    "docs/02-requirements/current-state-faic/FAIC-BASELINE.md",
    "docs/03-deliverables/G0-architecture-foundation/README.md",
]

MODULES = [
    "core", "master-data", "demand", "aps", "mes",
    "materials", "purchasing", "maintenance", "workforce", "intelligence"
]

def test_required_g0_documents_exist():
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    assert not missing, f"Missing G0 files: {missing}"

def test_module_placeholders_exist():
    missing = [m for m in MODULES if not (ROOT / "src/modules" / m / "README.md").exists()]
    assert not missing, f"Missing module placeholders: {missing}"
