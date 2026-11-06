"""Check read-only browser Materials scenario did not change physical or HOLD ledgers.

Runs inside the disposable runtime's API container AFTER Chrome completes.
"""
import json
from pathlib import Path
from sqlalchemy import func, select
from mop.config import Settings
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent
from mop.persistence.database import DatabaseManager

manifest = json.loads(Path("/tmp/g68_fixture/manifest.json").read_text(encoding="utf-8"))
db = DatabaseManager(Settings(environment="test", _env_file=None).database_url)
with db.session() as session:
    movements = session.scalar(select(func.count(MaterialMovement.id)))
    reservations = session.scalar(select(func.count(MaterialReservationEvent.id)))
assert movements == manifest["movement_count"], (
    "Browser material projection unexpectedly mutated inventory ledger",
    movements, manifest["movement_count"],
)
assert reservations == manifest["reservation_count"], (
    "Browser material projection unexpectedly mutated HOLD ledger",
    reservations, manifest["reservation_count"],
)
print("G6.8 materials browser read-only ledger invariants PASSED")
