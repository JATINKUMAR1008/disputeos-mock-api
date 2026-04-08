"""
End-to-end smoke check for the Supabase-backed DisputeStore.

Run AFTER `alembic upgrade head` has applied the initial schema:

    python smoke.py

The script uses a test-only dispute_id so it can clean up after itself
without touching real data. It exercises every public method on
`DisputeStore` and prints a pass/fail line for each step. Exits with a
non-zero status if any step fails so it can be wired into CI later.
"""

from __future__ import annotations

import sys
import traceback
import uuid
from datetime import datetime

from models import DisputeStateCreate, build_initial_record
from store import get_store

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []


def step(name: str):
    """Decorator to record pass/fail for a single smoke step."""

    def wrap(fn):
        def run():
            try:
                fn()
                results.append((name, True, ""))
                print(f"{GREEN}PASS{RESET}  {name}")
            except Exception as exc:  # noqa: BLE001 — smoke script, re-raise below
                results.append((name, False, f"{type(exc).__name__}: {exc}"))
                print(f"{RED}FAIL{RESET}  {name}")
                traceback.print_exc()

        return run

    return wrap


def main() -> int:
    store = get_store()
    # Unique ID so concurrent smoke runs can't collide.
    dispute_id = f"SMOKE-{uuid.uuid4().hex[:12]}"
    print(f"Using dispute_id={dispute_id!r}")

    @step("create")
    def _create():
        record = build_initial_record(DisputeStateCreate(dispute_id=dispute_id))
        created = store.create(dispute_id, record)
        assert created["dispute_id"] == dispute_id
        assert created["status"] == "intake"
        assert created["investigation_status"] == "pending"
        assert created["gate_1_status"] == "on_track"
        assert created["gate_2_status"] == "not_started"
        assert created["deadline_extended"] is False
        # created_at / updated_at are ISO strings, parseable by fromisoformat
        datetime.fromisoformat(created["created_at"])
        datetime.fromisoformat(created["updated_at"])

    @step("exists (true)")
    def _exists_true():
        assert store.exists(dispute_id) is True

    @step("get")
    def _get():
        row = store.get(dispute_id)
        assert row is not None
        assert row["dispute_id"] == dispute_id

    @step("count")
    def _count():
        assert store.count() >= 1

    @step("list_all contains dispute")
    def _list_all():
        rows = store.list_all()
        assert any(r["dispute_id"] == dispute_id for r in rows), (
            "smoke dispute not found in list_all()"
        )

    @step("create duplicate → ValueError")
    def _dup():
        record = build_initial_record(DisputeStateCreate(dispute_id=dispute_id))
        try:
            store.create(dispute_id, record)
        except ValueError:
            return
        raise AssertionError("Expected ValueError on duplicate create")

    @step("update existing")
    def _update():
        patch = {
            "status": "investigating",
            "investigation_status": "started",
            "gate_1_status": "completed",
            "investigation_deadline": 10,
            "deadline_extended": True,
            "user_written_notice": "smoke test notice",
        }
        updated = store.update(dispute_id, patch)
        assert updated is not None
        assert updated["status"] == "investigating"
        assert updated["investigation_status"] == "started"
        assert updated["gate_1_status"] == "completed"
        assert updated["investigation_deadline"] == 10
        assert updated["deadline_extended"] is True
        assert updated["user_written_notice"] == "smoke test notice"

    @step("update missing → None")
    def _update_missing():
        assert store.update("DOES-NOT-EXIST-xyz", {"status": "blocked"}) is None

    @step("delete existing → True")
    def _delete():
        assert store.delete(dispute_id) is True

    @step("delete missing → False")
    def _delete_missing():
        assert store.delete(dispute_id) is False

    @step("exists (false after delete)")
    def _exists_false():
        assert store.exists(dispute_id) is False

    for runner in [
        _create,
        _exists_true,
        _get,
        _count,
        _list_all,
        _dup,
        _update,
        _update_missing,
        _delete,
        _delete_missing,
        _exists_false,
    ]:
        runner()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print()
    print(f"Summary: {passed} passed, {failed} failed, {len(results)} total")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
