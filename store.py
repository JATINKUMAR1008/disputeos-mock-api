"""
SQLAlchemy-backed dispute state store.

Previously this module persisted dispute records to a JSON file on
disk; v3.0 moved the backing store to Postgres (Supabase). The public
interface is unchanged — `main.py` still calls `get_store()` and uses
`get / list_all / create / update / delete / exists / count / clear` —
so none of the HTTP layer had to change. Every method opens a fresh
session, runs exactly one transaction, and returns plain `dict`s so
callers never see ORM instances leak out of this module.

Concurrency: Uvicorn runs the app in a single async event loop. Each
`DisputeStore` call still does one blocking DB round-trip (FastAPI
schedules sync endpoint handlers on a threadpool). At mock-API scale
that's fine — endpoints each do one tiny transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import DisputeStateORM, orm_to_dict


def _utcnow() -> datetime:
    """Timezone-aware UTC now, for TIMESTAMPTZ columns."""
    return datetime.now(timezone.utc)


def _coerce_timestamp(value: Any) -> datetime | None:
    """Accept either a datetime or an ISO string (what `main.py` hands us)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # `fromisoformat` handles the `+00:00` suffix that `utcnow_iso()` emits.
        return datetime.fromisoformat(value)
    raise TypeError(f"Cannot coerce {type(value).__name__} to datetime")


class DisputeStore:
    """Row-per-dispute store backed by Postgres via SQLAlchemy."""

    # ─── Read operations ──────────────────────────────────────────────

    def get(self, dispute_id: str) -> dict[str, Any] | None:
        """Return the dispute record, or None if not found."""
        with SessionLocal() as session:
            row = session.get(DisputeStateORM, dispute_id)
            return orm_to_dict(row) if row is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all dispute records as a list of dicts."""
        with SessionLocal() as session:
            rows = session.execute(select(DisputeStateORM)).scalars().all()
            return [orm_to_dict(row) for row in rows]

    def exists(self, dispute_id: str) -> bool:
        """Return True if a row with this dispute_id exists."""
        with SessionLocal() as session:
            # SELECT 1 FROM disputes WHERE dispute_id = :id LIMIT 1
            result = session.execute(
                select(DisputeStateORM.dispute_id).where(
                    DisputeStateORM.dispute_id == dispute_id
                )
            ).first()
            return result is not None

    def count(self) -> int:
        """Return the total number of disputes."""
        with SessionLocal() as session:
            return session.execute(
                select(func.count()).select_from(DisputeStateORM)
            ).scalar_one()

    # ─── Write operations ─────────────────────────────────────────────

    def create(
        self, dispute_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new dispute record.

        Raises `ValueError` if a row with this dispute_id already exists,
        preserving the interface contract from the previous JSON-backed
        implementation.
        """
        kwargs = dict(data)
        # The caller passes dispute_id in two places (once as a positional arg
        # and once inside the dict); make sure they agree and don't double-set.
        kwargs.pop("dispute_id", None)
        kwargs["created_at"] = _coerce_timestamp(kwargs.get("created_at")) or _utcnow()
        kwargs["updated_at"] = _coerce_timestamp(kwargs.get("updated_at")) or _utcnow()

        row = DisputeStateORM(dispute_id=dispute_id, **kwargs)
        with SessionLocal() as session:
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    f"Dispute {dispute_id!r} already exists"
                ) from exc
            session.refresh(row)
            return orm_to_dict(row)

    def update(
        self, dispute_id: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Apply a partial update to an existing dispute record.

        Returns the updated record as a dict, or `None` if the dispute
        doesn't exist. `updated_at` is always overwritten with "now",
        matching the semantics of the PATCH endpoint.
        """
        with SessionLocal() as session:
            row = session.get(DisputeStateORM, dispute_id)
            if row is None:
                return None

            for key, value in patch.items():
                # Never let callers clobber the primary key or created_at.
                if key in ("dispute_id", "created_at"):
                    continue
                if key == "updated_at":
                    setattr(row, key, _coerce_timestamp(value))
                    continue
                if hasattr(row, key):
                    setattr(row, key, value)
                # Silently drop unknown keys — matches dict-merge behavior
                # of the old store, which would have happily stored them.

            # Caller may not have supplied updated_at in the patch; make
            # sure it reflects this write either way.
            row.updated_at = _utcnow()

            session.commit()
            session.refresh(row)
            return orm_to_dict(row)

    def delete(self, dispute_id: str) -> bool:
        """Delete a dispute. Returns True if deleted, False if not found."""
        with SessionLocal() as session:
            row = session.get(DisputeStateORM, dispute_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def clear(self) -> None:
        """Delete every dispute. Useful for tests and demos."""
        with SessionLocal() as session:
            session.execute(delete(DisputeStateORM))
            session.commit()


# Module-level singleton, same pattern as the previous implementation so
# `main.py` didn't need to change.
_store: DisputeStore | None = None


def get_store() -> DisputeStore:
    """Return the module-level DisputeStore instance."""
    global _store
    if _store is None:
        _store = DisputeStore()
    return _store
