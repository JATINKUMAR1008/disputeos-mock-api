# DisputeOS API

Two responsibilities in one FastAPI service:

1. **Dispute state store** — stateful JSON-file-backed store of dispute records keyed by `dispute_id`. Tracks the full timeline (gate statuses, compliance clock state, computed deadlines, investigation status). Called by the consumer intake form, the workflow's `agent_remediation` step, and the analyst dashboard view.

2. **Mock data sources** — deterministic synthetic account, transaction, and holiday-calendar data, generated from hash-seeded IDs. Used by the workflow's `data_source_calls` step for enrichment. These endpoints are stateless — the same ID always returns the same data.

> 📖 **Looking for full API documentation?** See **[API_DOCS.md](./API_DOCS.md)** or visit the **[live interactive Swagger docs](https://disputeos-mock-api.onrender.com/docs)**.

**Live deployment**: https://disputeos-mock-api.onrender.com

---

## Why This Exists

The DisputeOS workflow needs three external data sources:

1. **Account details** → drives `is_new_account`, `account_state` → drives `clock_variant`
2. **Transaction details** → drives `is_pos_debit`, `is_out_of_state` → drives `clock_variant`
3. **Holiday calendar** → drives business day calculation for deadlines

In production these would be real bank APIs. For the POC, this service simulates them with consistent synthetic data.

---

## Quick Start

### Option 1: Local Python

```bash
cd /Users/jatinkumar/Code/disputeos-mock-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8888
```

### Option 2: Docker Compose

```bash
cd /Users/jatinkumar/Code/disputeos-mock-api
docker compose up
```

### Verify

```bash
curl http://localhost:8888/health
# {"status": "ok"}

curl http://localhost:8888/
# Service info + endpoint list

# Open API docs in browser
open http://localhost:8888/docs
```

---

## Endpoints

### Dispute State Store (new in v2.0)

Stateful endpoints that store dispute records keyed by `dispute_id`. Data is persisted to a JSON file (`/tmp/disputeos_state.json` by default, override with `DISPUTE_STORE_PATH` env var).

#### `POST /api/disputes`
Create a new dispute. The body is just the `dispute_id` — the server initializes all status fields to `pending`, both deadlines to `null`, `deadline_extended` to `false`, and `user_written_notice` to `null`. Returns 409 if the `dispute_id` already exists.

```bash
curl -X POST https://disputeos-mock-api.onrender.com/api/disputes \
  -H "Content-Type: application/json" \
  -d '{"dispute_id": "DSP-2026-04-08-0001"}'
```

Initial state on creation:
```json
{
  "dispute_id": "DSP-2026-04-08-0001",
  "investigation_status": "pending",
  "gate_1_status": "pending",
  "gate_2_status": "pending",
  "investigation_deadline": null,
  "provisional_credit_status": "pending",
  "deadline_extended": false,
  "status": "pending",
  "user_written_notice": null,
  "written_notice_deadline": null,
  "created_at": "2026-04-08T08:07:27.619337+00:00",
  "updated_at": "2026-04-08T08:07:27.619337+00:00"
}
```

**Status fields** (`investigation_status`, `gate_1_status`, `gate_2_status`, `provisional_credit_status`, `status`) accept exactly one of: `pending`, `started`, `completed`. Anything else returns 422.

#### `GET /api/disputes`
List all disputes. Returns an array of full dispute records.

#### `GET /api/disputes/{dispute_id}`
Return the full state of a single dispute. 404 if not found.

#### `PATCH /api/disputes/{dispute_id}`
Shallow-merge a partial update into an existing dispute. Send only the fields you want to change.

```bash
curl -X PATCH https://disputeos-mock-api.onrender.com/api/disputes/DSP-2026-04-08-0001 \
  -H "Content-Type: application/json" \
  -d '{
    "investigation_status": "started",
    "investigation_deadline": 10,
    "gate_1_status": "completed",
    "user_written_notice": "Dear customer, your dispute is under review.",
    "written_notice_deadline": 7,
    "deadline_extended": true,
    "status": "started"
  }'
```

Fields with value `null` (or omitted) are **not applied** (treated as "unset" rather than "set to null"). Only non-null fields are merged into the existing record.

#### `DELETE /api/disputes/{dispute_id}`
Remove a dispute from the store. Returns 204 on success, 404 if not found.

---

### Mock Data Sources (unchanged from v1.0)

Stateless endpoints that generate deterministic synthetic data from hash-seeded IDs.

### `GET /api/mock/accounts/{account_id}`

Returns deterministic account details for any `account_id`.

**Example:**
```bash
curl http://localhost:8888/api/mock/accounts/ACC-884821
```

**Response:**
```json
{
  "account_id": "ACC-884821",
  "account_open_date": "2024-12-10",
  "account_age_days": 484,
  "account_type": "checking",
  "account_state": "CA",
  "is_new_account": false,
  "current_balance": 4218.50,
  "available_balance": 4218.50,
  "card_last_four": "4821",
  "card_network": "visa",
  "card_status": "active",
  "ach_enabled": true,
  "p2p_enrolled": true,
  "error_resolution_notice_provided": true
}
```

**Distribution:**
- 15% of accounts are < 30 days old (`is_new_account: true`)
- 70% checking, 30% savings
- 30 US states represented

---

### `GET /api/mock/transactions/{complaint_id}`

Returns deterministic transaction details for any `complaint_id`.

**Example:**
```bash
curl http://localhost:8888/api/mock/transactions/DSP-2026-04-07-0001
```

**With cross-state correlation:**
```bash
curl "http://localhost:8888/api/mock/transactions/DSP-2026-04-07-0001?account_id=ACC-884821"
```

When `account_id` is provided, `is_out_of_state` is computed correctly against the account's state.

**Response:**
```json
{
  "complaint_id": "DSP-2026-04-07-0001",
  "transaction_id": "TXN-20260403-984271",
  "transaction_date": "2026-04-03",
  "transaction_amount": 2340.00,
  "transaction_type": "atm",
  "merchant_name": "ATM #9284 - Chase",
  "merchant_state": "CA",
  "merchant_category_code": "6011",
  "is_pos_debit": false,
  "is_atm": true,
  "is_ach": false,
  "is_p2p": false,
  "is_out_of_state": false,
  "card_present": true,
  "card_network": null,
  "terminal_type": "atm",
  "entry_mode": "chip",
  "pin_verified": true,
  "auth_amount": 2340.00,
  "auth_response": "approved",
  "posted_date": "2026-04-03",
  "status": "posted"
}
```

**Distribution:**
- 40% `debit_card_pos`
- 25% `ach`
- 15% `atm`
- 10% `p2p`
- 5% `bill_pay`
- 5% `wire`
- 15% are out-of-state transactions

---

### `GET /api/mock/calendar/{year}`

Returns the Federal Reserve holiday calendar. Currently only `2026` is supported.

**Example:**
```bash
curl http://localhost:8888/api/mock/calendar/2026
```

**Response:**
```json
{
  "year": 2026,
  "institution": "default",
  "calendar_type": "federal_reserve",
  "holidays": [
    { "date": "2026-01-01", "name": "New Year's Day" },
    { "date": "2026-01-19", "name": "Birthday of Martin Luther King, Jr." },
    { "date": "2026-02-16", "name": "Washington's Birthday" },
    { "date": "2026-05-25", "name": "Memorial Day" },
    { "date": "2026-06-19", "name": "Juneteenth National Independence Day" },
    { "date": "2026-07-03", "name": "Independence Day (observed)" },
    { "date": "2026-09-07", "name": "Labor Day" },
    { "date": "2026-10-12", "name": "Columbus Day" },
    { "date": "2026-11-11", "name": "Veterans Day" },
    { "date": "2026-11-26", "name": "Thanksgiving Day" },
    { "date": "2026-12-25", "name": "Christmas Day" }
  ]
}
```

---

## Determinism

The same input always produces the same output. This is achieved by hashing the ID with SHA-256 and using the result as a random seed.

```python
def _seed_from_id(id_str: str) -> int:
    return int(hashlib.sha256(id_str.encode()).hexdigest(), 16) % (2**32)
```

This means:

- `ACC-884821` will always return the same account, every time, on every machine
- You don't need to seed any database
- Tests and demos are reproducible
- Different IDs produce different but consistent data

---

## Registering as Data Sources in the Workflow

Add these to Step 1 (Query Data) of the DisputeOS workflow wizard:

| Data Source Name | Type | URL | Method |
|---|---|---|---|
| `account_details_api` | API | `http://localhost:8888/api/mock/accounts/{{account_id}}` | GET |
| `transaction_details_api` | API | `http://localhost:8888/api/mock/transactions/{{complaint_id}}?account_id={{account_id}}` | GET |
| `holiday_calendar_api` | API | `http://localhost:8888/api/mock/calendar/2026` | GET |

The `{{account_id}}` and `{{complaint_id}}` placeholders are resolved by the platform from the dispute's entity schema fields at run time.

For deployment to a Kubernetes cluster, replace `localhost:8888` with the in-cluster service name (e.g., `http://disputeos-mock-api.default.svc.cluster.local:8888`).

---

## Project Structure

```
disputeos-mock-api/
├── main.py              # FastAPI app — state endpoints + mock data sources
├── store.py             # JSON-file-backed dispute state store
├── models.py            # Pydantic request/response models + initial state
├── generators.py        # Deterministic synthetic data generators (hash-seeded)
├── requirements.txt     # fastapi + uvicorn
├── Dockerfile           # Container image
├── docker-compose.yml   # One-command local startup
├── openapi.json         # OpenAPI 3.1 spec (auto-generated)
├── API_DOCS.md          # Full endpoint reference
├── .gitignore
└── README.md            # This file
```

## ⚠️ Persistence Note (Render Free Tier)

The dispute state store uses a JSON file at `/tmp/disputeos_state.json` by default. On Render's free tier, the container's filesystem is **ephemeral** — when the container restarts (after ~15 min of inactivity or on a new deploy), the state is wiped.

For a POC this is acceptable since demos happen within a single session. For persistence across restarts, set `DISPUTE_STORE_PATH` to a Render persistent disk mount, or swap the `DisputeStore` class in `store.py` for a Postgres-backed implementation (Neon/Supabase free tier both work).

---

## Adding More Data Sources

To add another mock endpoint:

1. Add a generator function in `generators.py`
2. Add the route in `main.py`
3. Update the README

Generators must be **deterministic** — use `_seeded_random(id)` to get a Random instance seeded by the input ID.

---

## License

Internal MightyBot POC. Not for distribution.
