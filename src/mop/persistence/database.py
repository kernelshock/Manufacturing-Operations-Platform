"""Database engine and session lifecycle."""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseManager:
    """Own the SQLAlchemy engine and unit-of-work session factory."""

    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    def session(self) -> Iterator[Session]:
        """Yield a transactional session and always close it."""

        with self.session_factory() as db_session:
            yield db_session

    def check_connection(self) -> None:
        """Raise when the database cannot execute a minimal query."""

        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        """Release pooled database resources."""

        self.engine.dispose()
