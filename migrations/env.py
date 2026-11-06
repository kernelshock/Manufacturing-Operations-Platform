"""Alembic migration environment."""

from alembic import context
from sqlalchemy import create_engine, pool

from mop.aps import models as aps_models  # noqa: F401
from mop.aps import operation_models as aps_operation_models  # noqa: F401
from mop.aps import capacity_models as aps_capacity_models  # noqa: F401
from mop.aps import schedule_models as aps_schedule_models  # noqa: F401
from mop.aps import lifecycle_models as aps_lifecycle_models  # noqa: F401
from mop.aps import whatif_models as aps_whatif_models  # noqa: F401
from mop.audit import models as audit_models  # noqa: F401
from mop.config import get_settings
from mop.core import models as core_models  # noqa: F401
from mop.demand import models as demand_models  # noqa: F401
from mop.iam import models as iam_models  # noqa: F401
from mop.master_data import models as master_data_models  # noqa: F401
from mop.materials import models as materials_models  # noqa: F401
from mop.materials import consumption_models as materials_consumption_models  # noqa: F401
from mop.materials import reservation_models as materials_reservation_models  # noqa: F401
from mop.mes import models as mes_models  # noqa: F401
from mop.mes import rework_models as mes_rework_models  # noqa: F401
from mop.prolowin import models as prolowin_models  # noqa: F401
from mop.prolowin import procurement_models as prolowin_procurement_models  # noqa: F401
from mop.persistence.base import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    settings = get_settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = get_settings()
    connectable = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
