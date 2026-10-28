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
    "docs/01-architecture/ADR/ADR-0005-prolowin-system-of-record.md",
    "docs/01-architecture/ADR/ADR-0006-prolowin-file-integration.md",
    "docs/01-architecture/ADR/ADR-0007-physical-kanban-operational-inventory.md",
    "docs/01-architecture/ADR/ADR-0008-legacy-reorder-values-non-authoritative.md",
    "docs/01-architecture/ADR/ADR-0009-prospective-recalibration-baseline.md",
    "docs/01-architecture/ADR/ADR-0010-weekly-plan-taquilla-demand-source.md",
    "docs/01-architecture/ADR/ADR-0011-separate-bom-from-bop-routing.md",
    "docs/01-architecture/ADR/ADR-0012-prolowin-complete-report-fin-normalization.md",
    "docs/01-architecture/domain-model/CANONICAL-DOMAIN-MODEL.md",
    "docs/01-architecture/event-catalog/EVENT-CATALOG.md",
    "docs/01-architecture/modules/MODULE-MAP.md",
    "docs/01-architecture/system-of-record/SYSTEM-OF-RECORD.md",
    "docs/02-requirements/current-state-faic/FAIC-BASELINE.md",
    "docs/02-requirements/current-state-faic/MATERIAL-REPLENISHMENT-FLOW.md",
    "docs/02-requirements/materials/E-KANBAN-FUNCTIONAL-MODEL.md",
    "docs/02-requirements/materials/BASELINE-RECALIBRATION-REQUIREMENT.md",
    "docs/02-requirements/materials/PLAN-TAQUILLA-DEMAND-DERIVATION.md",
    "docs/03-deliverables/G0-architecture-foundation/README.md",
    "docs/02-requirements/master-data/samples/PROLOWIN-X-2209-COMPLETE-STRUCTURE.md",
    "docs/02-requirements/master-data/samples/PROLOWIN-X-6111-COMPLETE-STRUCTURE.md",
    "docs/02-requirements/master-data/samples/PROLOWIN-X-7070-COMPLETE-STRUCTURE.md",
    "docs/04-reference/faic-legacy/LEGACY-REORDER-POINT-METHOD-ANALYSIS.md",
    "docs/04-reference/faic-prolowin-samples/SOURCE-MANIFEST.md",
    "docs/04-reference/faic-prolowin-samples/PROLOWIN-REFERENCE-CORPUS-ANALYSIS.md",
    "integrations/prolowin/INTEGRATION-BASELINE.md",
    "docs/01-architecture/security/SECURITY-RESILIENCE-BASELINE.md",
    "infrastructure/deployment/FAIC-REFERENCE-TOPOLOGY.md",
    "docs/01-architecture/ADR/ADR-0018-single-tenant-multi-plant.md",
    "docs/01-architecture/ADR/ADR-0017-backup-restore-retention.md",
    "docs/01-architecture/ADR/ADR-0016-authentication-authorization-baseline.md",
    "docs/01-architecture/ADR/ADR-0015-initial-deployment-topology.md",
    "docs/01-architecture/ADR/ADR-0014-application-technology-stack.md",
    "integrations/prolowin/contracts/complete-structure-batch.schema.json",
    "integrations/prolowin/contracts/IMPORT-CONTRACT.md",
    "docs/00-governance/data-handling/REPOSITORY-DATA-BOUNDARY.md",
    "docs/02-requirements/master-data/PROLOWIN-ASSIMILATION-ACCEPTANCE-CRITERIA.md",
    "docs/01-architecture/data-model/MASTER-DATA-BOM-BOP-PHYSICAL-SCHEMA.md",
    "docs/01-architecture/ADR/ADR-0013-master-data-owns-manufacturing-definition.md",
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
