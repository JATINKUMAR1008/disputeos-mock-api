# DisputeOS Mock API — Full Documentation

Mock data source endpoints for the DisputeOS workflow POC. The MightyBot platform's `data_source_calls` step hits these endpoints during workflow runs to enrich dispute records with account, transaction, and calendar data.

**Base URL**: https://disputeos-mock-api.onrender.com
**Interactive docs**: https://disputeos-mock-api.onrender.com/docs (Swagger UI)
**OpenAPI spec**: https://disputeos-mock-api.onrender.com/openapi.json
**Source code**: https://github.com/JATINKUMAR1008/disputeos-mock-api

---

## Table of Contents

- [How Data Generation Works](#how-data-generation-works)
- [Endpoints](#endpoints)
  - [Service Info](#1-service-info)
  - [Health Check](#2-health-check)
  - [Account Details](#3-account-details)
  - [Transaction Details](#4-transaction-details)
  - [Holiday Calendar](#5-holiday-calendar)
- [Workflow Wizard Configuration](#workflow-wizard-configuration)
- [Example Flow](#example-flow)
- [Testing Recipes](#testing-recipes)
- [Important Notes](#important-notes)

---

## How Data Generation Works

Every endpoint that takes an ID (`account_id`, `complaint_id`) uses the ID itself as a **deterministic seed** for data generation:

```
Input ID → SHA-256 hash → 32-bit integer → random.Random(seed) → consistent data
```

**Properties:**

- **Same ID always returns the same data** — call it 1000 times, get the same response
- **Different IDs return different but consistent data**
- **No database, no storage, no state**
- **Works on any machine** — the hash is the same everywhere
- **Pass any ID format** — `ACC-884821`, `123456`, `customer-foo-bar`, all work

This is why you don't need to "create" records first — just pass any string and the generator produces a record for it. The same ID produces the exact same record on every call.

---

## Endpoints

### 1. Service Info

#### `GET /`

Returns service metadata and endpoint discovery.

**Request:**

```bash
curl https://disputeos-mock-api.onrender.com/
```

**Response (200):**

```json
{
  "service": "disputeos-mock-api",
  "version": "1.0.0",
  "description": "Mock data sources for DisputeOS workflow POC",
  "endpoints": [
    {
      "path": "/api/mock/accounts/{account_id}",
      "method": "GET",
      "description": "Deterministic account details for any account_id"
    },
    {
      "path": "/api/mock/transactions/{complaint_id}",
      "method": "GET",
      "description": "Deterministic transaction details for any complaint_id",
      "query_params": {
        "account_id": "Optional — passes account state for is_out_of_state computation"
      }
    },
    {
      "path": "/api/mock/calendar/{year}",
      "method": "GET",
      "description": "Federal Reserve holiday calendar (2026 only)"
    }
  ]
}
```

---

### 2. Health Check

#### `GET /health`

Liveness probe. Use this for uptime monitoring or to "wake up" the service after Render's free-tier sleep.

**Request:**

```bash
curl https://disputeos-mock-api.onrender.com/health
```

**Response (200):**

```json
{ "status": "ok" }
```

---

### 3. Account Details

#### `GET /api/mock/accounts/{account_id}`

Returns deterministic account details for any `account_id`.

**Path Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `account_id` | string | yes | Any string. Pass the account ID from your dispute. Format doesn't matter (`ACC-884821`, `12345`, `my-acct-foo`). |

**Query Parameters:** none

**Request:**

```bash
curl https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821
```

**Response (200):**

```json
{
  "account_id": "ACC-884821",
  "account_open_date": "2024-09-05",
  "account_age_days": 579,
  "account_type": "checking",
  "account_state": "CO",
  "is_new_account": false,
  "current_balance": 22740.7,
  "available_balance": 7867.0,
  "card_last_four": "4821",
  "card_network": "visa",
  "card_status": "active",
  "ach_enabled": true,
  "p2p_enrolled": true,
  "error_resolution_notice_provided": true
}
```

**Field Reference:**

| Field | Type | Generation Logic |
|---|---|---|
| `account_id` | string | Echo of the input |
| `account_open_date` | ISO date | `today - account_age_days` |
| `account_age_days` | int | **15% chance**: 1-29 days (`is_new_account=true`)<br>**85% chance**: ~30 days to ~5 years (normal distribution, mean=600, std=400) |
| `account_type` | enum | `checking` (70%) or `savings` (30%) |
| `account_state` | string | One of 30 US states (uniform random) |
| `is_new_account` | bool | `account_age_days < 30` — drives `clock_variant = new_account_20` |
| `current_balance` | decimal | $500-$25,000 (uniform) |
| `available_balance` | decimal | $500-$25,000 (uniform) |
| `card_last_four` | string | Last 4 digits of `account_id` if numeric, else random |
| `card_network` | enum | `visa` or `mastercard` (50/50) |
| `card_status` | string | Always `"active"` |
| `ach_enabled` | bool | Always `true` |
| `p2p_enrolled` | bool | 60% true |
| `error_resolution_notice_provided` | bool | Always `true` (compliance baseline — if `false`, consumer liability = $0) |

**Errors:**

- `400` — `account_id` is empty or whitespace

**Determinism guarantee:**

```bash
# These two calls always return identical responses
curl https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821
curl https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821
```

---

### 4. Transaction Details

#### `GET /api/mock/transactions/{complaint_id}`

Returns deterministic transaction details for any `complaint_id`. Optionally cross-correlates with an `account_id` for accurate `is_out_of_state` computation.

**Path Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `complaint_id` | string | yes | Any string. Pass the dispute/complaint ID. Format doesn't matter (`DSP-2026-04-07-0001`, `disp-001`, etc.). |

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `account_id` | string | no | If provided, the merchant_state is computed against the account's state. Without this, `merchant_state` is independent random. |

**Request (without account):**

```bash
curl https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-2026-04-07-0001
```

**Request (with account correlation — recommended):**

```bash
curl "https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-2026-04-07-0001?account_id=ACC-884821"
```

**Response (200):**

```json
{
  "complaint_id": "DSP-2026-04-07-0001",
  "transaction_id": "TXN-20260403-208041",
  "transaction_date": "2026-04-03",
  "transaction_amount": 5091.41,
  "transaction_type": "debit_card_pos",
  "merchant_name": "Walmart SC #332",
  "merchant_state": "CO",
  "merchant_category_code": "5999",
  "is_pos_debit": true,
  "is_atm": false,
  "is_ach": false,
  "is_p2p": false,
  "is_out_of_state": false,
  "card_present": true,
  "card_network": "mastercard",
  "terminal_type": "pos",
  "entry_mode": "contactless",
  "pin_verified": false,
  "auth_amount": 5091.41,
  "auth_response": "approved",
  "posted_date": "2026-04-03",
  "status": "posted"
}
```

**Field Reference:**

| Field | Type | Generation Logic |
|---|---|---|
| `complaint_id` | string | Echo of the input |
| `transaction_id` | string | Format: `TXN-{YYYYMMDD}-{6-digit-suffix}`, deterministic |
| `transaction_date` | ISO date | 1-14 days before today |
| `transaction_amount` | decimal | Type-specific range (see below) |
| `transaction_type` | enum | Weighted random (see distribution below) |
| `merchant_name` | string | Random from a pool matching the transaction type |
| `merchant_state` | string | If `account_id` passed: matches account state (or different if `is_out_of_state=true`). Otherwise random. |
| `merchant_category_code` | string | MCC code based on transaction type (`6011` for ATM, `5999` for POS, etc.) |
| `is_pos_debit` | bool | `transaction_type == "debit_card_pos"` — drives `clock_variant=pos_90` |
| `is_atm` | bool | `transaction_type == "atm"` |
| `is_ach` | bool | `transaction_type == "ach"` |
| `is_p2p` | bool | `transaction_type == "p2p"` |
| `is_out_of_state` | bool | 15% chance — drives `clock_variant=out_of_state_90` |
| `card_present` | bool | `true` for ATM, 70% for POS, `false` otherwise |
| `card_network` | enum/null | `visa`/`mastercard` for POS, `null` otherwise |
| `terminal_type` | string | `atm`, `pos`, `ach_network`, `p2p_app`, `wire_network`, or `online` |
| `entry_mode` | enum | `chip` (ATM), random for POS, `online` otherwise |
| `pin_verified` | bool | `true` for ATM, 50% for POS, `false` otherwise |
| `auth_amount` | decimal | Same as `transaction_amount` |
| `auth_response` | string | Always `"approved"` |
| `posted_date` | ISO date | Same as `transaction_date` |
| `status` | string | Always `"posted"` |

**Transaction Type Distribution:**

| Type | Weight | Amount Range | Notes |
|---|---|---|---|
| `debit_card_pos` | 40% | $25 - $8,000 | POS transactions → triggers `pos_90` clock variant |
| `ach` | 25% | $100 - $15,000 | ACH transfers (bills, payroll) |
| `atm` | 15% | $60 - $3,000 | ATM withdrawals |
| `p2p` | 10% | $50 - $5,000 | Zelle / Venmo / Cash App |
| `bill_pay` | 5% | $50 - $3,000 | Bill payments |
| `wire` | 5% | $1,000 - $50,000 | Wire transfers |

**Determinism guarantee (cross-state correlation):**

The `transaction_id`, `transaction_date`, `transaction_amount`, `transaction_type`, and `merchant_name` are **identical** whether or not you pass `account_id`. Only `merchant_state` and `is_out_of_state` change based on the account context.

```bash
# These return the same transaction_id, date, amount, type, merchant
curl https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-001
curl "https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-001?account_id=ACC-884821"
```

**Errors:**

- `400` — `complaint_id` is empty or whitespace

---

### 5. Holiday Calendar

#### `GET /api/mock/calendar/{year}`

Returns the Federal Reserve holiday calendar for the given year. Used by the workflow's collation step for business day calculation (Reg E investigation deadlines are in business days, which skip weekends and federal holidays).

**Path Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `year` | int | yes | Currently only `2026` is supported. Other years return 404. |

**Request:**

```bash
curl https://disputeos-mock-api.onrender.com/api/mock/calendar/2026
```

**Response (200):**

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

**Errors:**

- `404` — Year is not 2026

```bash
# Returns 404
curl https://disputeos-mock-api.onrender.com/api/mock/calendar/2025
# {"detail": "Holiday calendar for year 2025 not available. Only 2026 supported."}
```

---

## Workflow Wizard Configuration

Add these three Data Sources in **Step 1: Query Data** of the DisputeOS workflow:

### Data Source 1: Account Details

| Field | Value |
|---|---|
| **Name** | `account_details_api` |
| **Type** | `API` |
| **Method** | `GET` |
| **Base URL** | `https://disputeos-mock-api.onrender.com/api/mock/accounts/{{account_id}}` |
| **Auth** | None |
| **Variables** | `account_id` resolved from `dispute_intake.account_id` |

### Data Source 2: Transaction Details

| Field | Value |
|---|---|
| **Name** | `transaction_details_api` |
| **Type** | `API` |
| **Method** | `GET` |
| **Base URL** | `https://disputeos-mock-api.onrender.com/api/mock/transactions/{{complaint_id}}?account_id={{account_id}}` |
| **Auth** | None |
| **Variables** | `complaint_id` from `dispute_intake.complaint_id`, `account_id` from `dispute_intake.account_id` |

### Data Source 3: Holiday Calendar

| Field | Value |
|---|---|
| **Name** | `holiday_calendar_api` |
| **Type** | `API` |
| **Method** | `GET` |
| **Base URL** | `https://disputeos-mock-api.onrender.com/api/mock/calendar/2026` |
| **Auth** | None |
| **Variables** | none |

---

## Example Flow

```
1. Consumer files dispute via webhook:
   POST /api/definitions/{def_id}/instances/webhook
   {
     "complaint_id": "DSP-2026-04-07-0001",
     "account_id": "ACC-884821",
     "consumer_name": "Maria Chen",
     ...
   }

2. Platform creates instance, runs full workflow

3. Step 1 (Query Data) calls these endpoints:

   GET https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821
       → Returns: {
           account_age_days: 579,
           account_state: "CO",
           is_new_account: false,
           ...
         }

   GET https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-2026-04-07-0001?account_id=ACC-884821
       → Returns: {
           transaction_type: "debit_card_pos",
           is_pos_debit: true,
           is_out_of_state: false,
           merchant_state: "CO",
           ...
         }

   GET https://disputeos-mock-api.onrender.com/api/mock/calendar/2026
       → Returns: {holidays: [...]}

4. Step 4 (Collation) uses these to compute:
   clock_variant = "pos_90"  (because is_pos_debit=true)
   investigation_deadline = intake_date + 10 business days (skipping holidays)

5. Step 5 (Policies) evaluates gates against deadlines

6. Frontend reads run.result_data.step_data for current state
```

---

## Testing Recipes

### Quick Test All Endpoints

```bash
#!/bin/bash
BASE="https://disputeos-mock-api.onrender.com"

echo "1. Health check"
curl -s "$BASE/health"
echo

echo "2. Account details"
curl -s "$BASE/api/mock/accounts/ACC-884821" | python3 -m json.tool
echo

echo "3. Transaction with cross-state correlation"
curl -s "$BASE/api/mock/transactions/DSP-2026-04-07-0001?account_id=ACC-884821" | python3 -m json.tool
echo

echo "4. Holiday calendar"
curl -s "$BASE/api/mock/calendar/2026" | python3 -m json.tool
```

### Find a New Account (age < 30 days)

```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -s "https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-NEW-$i" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"account_id\"]}: new={d[\"is_new_account\"]} age={d[\"account_age_days\"]}')"
done
```

### Find a POS Debit Transaction

```bash
for i in 1 2 3 4 5; do
  curl -s "https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-POS-$i" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"complaint_id\"]}: type={d[\"transaction_type\"]} amount=\${d[\"transaction_amount\"]}')"
done
```

### Verify Determinism

```bash
# Should print "IDENTICAL" if working correctly
A=$(curl -s "https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821")
B=$(curl -s "https://disputeos-mock-api.onrender.com/api/mock/accounts/ACC-884821")
[ "$A" = "$B" ] && echo "IDENTICAL ✓" || echo "DIFFERENT ✗"
```

### Verify Cross-State Correlation

```bash
# transaction_id, date, amount, type, merchant should be IDENTICAL
# Only merchant_state and is_out_of_state should differ
curl -s "https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-001" | python3 -m json.tool
curl -s "https://disputeos-mock-api.onrender.com/api/mock/transactions/DSP-001?account_id=ACC-884821" | python3 -m json.tool
```

---

## Important Notes

### Render Free Tier Sleep

The service sleeps after **15 minutes of inactivity**. The first request after sleep takes ~30 seconds to wake up. Subsequent requests are fast (~200-500ms).

**To keep it warm during demos**, ping `/health` every 10 minutes from a cron service like [cron-job.org](https://cron-job.org) or [uptimerobot.com](https://uptimerobot.com).

### CORS

CORS is set to `*` (open) for development. Lock it down to your workflow service domain before any production-like usage.

### Year Support

Only 2026 holidays are loaded. Add more years to `FED_HOLIDAYS_2026` in `generators.py` if you need them.

### Error Resolution Notice Field

The `error_resolution_notice_provided` field on accounts is always `true`. In real Reg E compliance, if a bank fails to provide an error resolution notice, the consumer's liability for unauthorized transfers becomes **$0** regardless of when they reported the loss. We default to `true` to keep the POC focused on the gate enforcement scenarios.

---

## Quick Links

- **Live API**: https://disputeos-mock-api.onrender.com
- **Interactive docs**: https://disputeos-mock-api.onrender.com/docs
- **OpenAPI JSON**: https://disputeos-mock-api.onrender.com/openapi.json
- **GitHub repo**: https://github.com/JATINKUMAR1008/disputeos-mock-api
- **Health check**: https://disputeos-mock-api.onrender.com/health

---

*Last updated: 2026-04-07*
