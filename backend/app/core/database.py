"""Database foundation.

Uses SQLAlchemy 2.x with a URL-driven engine so switching from SQLite (local
development) to PostgreSQL (deployment) is a configuration change, not a code
change. All timestamps are stored in UTC.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine, Index, inspect as sqlalchemy_inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base for all KESHAV ORM models."""


_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    from .. import models  # noqa: F401  ensure models are registered

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        # Sqlite may raise OperationalError if index already exists from
        # a previous run. Attempt idempotent index creation below.
        _ensure_indexes(engine)
    _apply_idempotent_migrations(engine)


def _ensure_indexes(eng) -> None:
    """Ensure required indexes exist, creating only those that are missing.

    Sqlite does not support CREATE INDEX IF NOT EXISTS, so we attempt
    creation and silently ignore "already exists" errors.

    Uses SQLAlchemy 2.x API: pass column objects directly to Index()
    instead of the deprecated column_list keyword argument.
    """
    from sqlalchemy import Table as SATable, inspect
    from sqlalchemy.engine import reflection

    inspector = inspect(eng)

    # Define required indexes per table (name, table_name, column_list)
    required_indexes = [
        ("ix_risk_predictions_location_time", "risk_predictions", ["location_id", "target_date"]),
        ("ix_risk_predictions_model_version", "risk_predictions", ["model_version"]),
        ("ix_risk_predictions_horizon", "risk_predictions", ["horizon_days"]),
        ("ix_risk_model_registry_model_id", "risk_model_registry", ["model_id"]),
        ("ix_risk_model_registry_model_version", "risk_model_registry", ["model_version"]),
        ("ix_risk_explanations_prediction_id", "risk_explanations", ["prediction_id"]),
        ("ix_risk_explanations_ood", "risk_explanations", ["ood"]),
        ("ix_feature_importance_model_version", "feature_importance", ["model_version", "explanation_method"]),
        ("ix_uncertainty_prediction_id", "uncertainty_records", ["prediction_id"]),
        ("ix_uncertainty_data_quality", "uncertainty_records", ["data_quality"]),
        ("ix_ood_prediction_id", "ood_records", ["prediction_id"]),
        ("ix_ood_in_distribution", "ood_records", ["in_distribution"]),
        ("ix_calibration_model_version", "calibration_diagnostics", ["model_version"]),
        ("ix_equity_model_version_subgroup", "equity_audits", ["model_version", "subgroup"]),
        ("ix_equity_sufficient_sample", "equity_audits", ["sufficient_sample"]),
    ]

    for idx_name, tbl_name, cols in required_indexes:
        try:
            existing = inspector.get_indexes(tbl_name)
            idx_exists = any(
                idx["name"] == idx_name for idx in existing
            )
            if not idx_exists:
                with eng.begin() as conn:
                    # Reflect table and use column objects directly
                    # to avoid the deprecated column_list keyword argument
                    ref_table = SATable(tbl_name, eng.schema_metadata, autoload_with=eng)
                    col_objects = [ref_table.c[col] for col in cols if col in ref_table.c]
                    if col_objects:
                        Index(idx_name, *col_objects, unique=False).create(conn)
        except Exception:
            # Silently ignore - index may have been created by another process
            pass


_MIGRATION_COLUMNS = {
    "ingestion_logs": [
        ("request_id", "VARCHAR(64)"),
        ("ingestion_id", "VARCHAR(64)"),
        ("duration_ms", "INTEGER"),
        ("fallback_used", "BOOLEAN"),
        ("fallback_source", "VARCHAR(64)"),
    ],
}


def _apply_idempotent_migrations(eng) -> None:
    """Add nullable columns that landed in a later Step without breaking
    existing SQLite databases (CREATE TABLE-only workflows otherwise leave
    previously created tables without the new columns)."""
    db_engine = eng.url.get_backend_name()
    if db_engine != "sqlite":
        return
    try:
        inspector = __import__("sqlalchemy").inspect(eng)
        for table, columns in _MIGRATION_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)} if _table_exists(inspector, table) else set()
            for col_name, col_type in columns:
                if col_name in existing:
                    continue
                with eng.begin() as conn:
                    conn.execute(
                        __import__(
                            "sqlalchemy"
                        ).text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    )
    except Exception:  # pragma: no cover - migration must never break startup
        import logging

        logging.getLogger("keshav.database").exception("idempotent migration failed")


def _table_exists(inspector, table: str) -> bool:
    try:
        return table in inspector.get_table_names()
    except Exception:  # pragma: no cover
        return False


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()