"""
Simple JSON-file-backed dispute state store.

Single dict keyed by dispute_id, persisted to a JSON file on every mutation.
Atomic writes via tempfile-rename pattern so a crash mid-write can't corrupt
the file.

Not thread-safe in the strict sense, but since Uvicorn runs this in a single
async event loop, concurrent mutations are naturally serialized.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Default path — /tmp is writable on every free-tier host including Render.
# Override with DISPUTE_STORE_PATH env var in production.
DEFAULT_STORE_PATH = Path(os.environ.get("DISPUTE_STORE_PATH", "/tmp/disputeos_state.json"))


class DisputeStore:
    """JSON-file-backed key-value store for dispute state.

    State shape:
        {
            "DSP-2026-04-08-0001": { ...full dispute state... },
            "DSP-2026-04-08-0002": { ...full dispute state... },
            ...
        }
    """

    def __init__(self, path: Path = DEFAULT_STORE_PATH) -> None:
        self.path = path
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk. Creates an empty store if the file doesn't exist."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupt or unreadable file — start fresh rather than crash
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Atomically persist state to disk using a tempfile + rename.

        Rename is atomic on POSIX so readers never see a half-written file.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=".disputeos_", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(self._data, f, indent=2, default=str, sort_keys=True)
            os.replace(tmp_name, self.path)
        except Exception:
            # Best-effort cleanup if something went wrong before the rename
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ─── Read operations ──────────────────────────────────────────────

    def get(self, dispute_id: str) -> dict[str, Any] | None:
        """Return the dispute record, or None if not found."""
        record = self._data.get(dispute_id)
        return dict(record) if record is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all dispute records as a list."""
        return [dict(v) for v in self._data.values()]

    def exists(self, dispute_id: str) -> bool:
        return dispute_id in self._data

    def count(self) -> int:
        return len(self._data)

    # ─── Write operations ─────────────────────────────────────────────

    def create(self, dispute_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new dispute record. Raises ValueError if already exists."""
        if dispute_id in self._data:
            raise ValueError(f"Dispute {dispute_id!r} already exists")
        self._data[dispute_id] = dict(data)
        self._save()
        return dict(self._data[dispute_id])

    def upsert(self, dispute_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create or fully replace a dispute record."""
        self._data[dispute_id] = dict(data)
        self._save()
        return dict(self._data[dispute_id])

    def update(
        self, dispute_id: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Shallow-merge patch into an existing dispute record.

        Returns the updated record, or None if the dispute doesn't exist.
        Keys in patch with value None are INCLUDED in the merge (they'll
        overwrite existing values). Callers should filter None values
        before calling if they want true partial-update semantics.
        """
        if dispute_id not in self._data:
            return None
        self._data[dispute_id] = {**self._data[dispute_id], **patch}
        self._save()
        return dict(self._data[dispute_id])

    def delete(self, dispute_id: str) -> bool:
        """Delete a dispute. Returns True if deleted, False if not found."""
        if dispute_id not in self._data:
            return False
        del self._data[dispute_id]
        self._save()
        return True

    def clear(self) -> None:
        """Delete all disputes. Useful for tests / demos."""
        self._data = {}
        self._save()


# Module-level singleton — initialized lazily on first import in main.py
_store: DisputeStore | None = None


def get_store() -> DisputeStore:
    """Return the module-level store instance. Safe to call multiple times."""
    global _store
    if _store is None:
        _store = DisputeStore()
    return _store
