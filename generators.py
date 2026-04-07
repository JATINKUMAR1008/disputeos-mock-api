"""
Deterministic data generators for the DisputeOS mock API.

Each generator takes an ID and returns a dict. The same ID always returns
the same data (hash-seeded random), so no storage is needed and the API
remains stateless.
"""

import hashlib
import random
from datetime import date, timedelta


# ─── SEED HELPERS ──────────────────────────────────────────────────────────

def _seed_from_id(id_str: str) -> int:
    """Create a deterministic 32-bit integer seed from any string ID."""
    return int(hashlib.sha256(id_str.encode()).hexdigest(), 16) % (2**32)


def _seeded_random(id_str: str) -> random.Random:
    """Get a Random instance seeded by the ID. Same ID → same sequence."""
    return random.Random(_seed_from_id(id_str))


# ─── DATA POOLS ────────────────────────────────────────────────────────────

US_STATES = [
    "CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT",
]

CARD_NETWORKS = ["visa", "mastercard"]
ACCOUNT_TYPES = ["checking", "savings"]

ATM_MERCHANTS = [
    "ATM #9284 - Chase",
    "ATM #3311 - BofA",
    "ATM #6677 - Wells Fargo",
    "ATM Non-Network #4420",
    "ATM #5592 - WF",
    "ATM #8821 - Citibank",
    "ATM #1145 - Capital One",
]

POS_MERCHANTS = [
    "BestBuy #4102",
    "Target #1890",
    "Amazon.com",
    "Walmart SC #332",
    "Costco Wholesale #209",
    "Home Depot #2891",
    "Starbucks #14203",
    "Whole Foods #221",
    "Apple Store #001",
    "Trader Joe's #455",
    "CVS Pharmacy #883",
    "Shell Gas Station #7741",
]

ACH_MERCHANTS = [
    "ElectricCo Utility",
    "Unknown ACH Originator",
    "XYZ Corp Payroll",
    "StateAuto Insurance",
    "Verizon Wireless",
    "Comcast Cable",
    "Geico Insurance",
    "Wells Fargo Mortgage",
]

P2P_MERCHANTS = [
    "Zelle to 'Mike R.'",
    "Zelle to 'unknown'",
    "Venmo @seller2934",
    "Cash App $username",
    "Zelle to 'Sarah K.'",
]

WIRE_MERCHANTS = [
    "Wire Transfer - International",
    "Wire Transfer - Domestic",
    "Title Company Escrow",
]

BILL_PAY_MERCHANTS = [
    "City Water Department",
    "State Tax Authority",
    "Property Management LLC",
    "Health Insurance Premium",
]


# ─── ACCOUNT GENERATOR ─────────────────────────────────────────────────────

def generate_account(account_id: str) -> dict:
    """
    Generate deterministic account details from an account_id.

    Distribution:
      - 15% new accounts (< 30 days old)
      - 70% checking, 30% savings
      - Account ages spread realistically (most 6 months to 5 years)
    """
    rng = _seeded_random(account_id)

    # 15% chance of new account
    is_new = rng.random() < 0.15
    if is_new:
        # 1-29 days old
        account_age_days = rng.randint(1, 29)
    else:
        # 30 days to ~5 years, normal-ish distribution
        account_age_days = max(30, int(rng.gauss(600, 400)))

    account_open_date = (date.today() - timedelta(days=account_age_days)).isoformat()

    # Card last four — extract from account_id if possible, else random
    digits = "".join(c for c in account_id if c.isdigit())
    if len(digits) >= 4:
        card_last_four = digits[-4:]
    else:
        card_last_four = f"{rng.randint(0, 9999):04d}"

    return {
        "account_id": account_id,
        "account_open_date": account_open_date,
        "account_age_days": account_age_days,
        "account_type": rng.choices(ACCOUNT_TYPES, weights=[70, 30])[0],
        "account_state": rng.choice(US_STATES),
        "is_new_account": is_new,
        "current_balance": round(rng.uniform(500, 25000), 2),
        "available_balance": round(rng.uniform(500, 25000), 2),
        "card_last_four": card_last_four,
        "card_network": rng.choice(CARD_NETWORKS),
        "card_status": "active",
        "ach_enabled": True,
        "p2p_enrolled": rng.random() < 0.6,
        "error_resolution_notice_provided": True,
    }


# ─── TRANSACTION GENERATOR ─────────────────────────────────────────────────

def generate_transaction(complaint_id: str, account_state: str | None = None) -> dict:
    """
    Generate deterministic transaction details from a complaint_id.

    Optionally takes account_state to compute is_out_of_state correctly
    (15% of transactions occur in a different state from the account).

    Distribution:
      - 40% debit_card_pos
      - 25% ach
      - 15% atm
      - 10% p2p
      - 5%  bill_pay
      - 5%  wire
    """
    rng = _seeded_random(complaint_id)

    # Pick transaction type with realistic distribution
    txn_type = rng.choices(
        ["debit_card_pos", "ach", "atm", "p2p", "bill_pay", "wire"],
        weights=[40, 25, 15, 10, 5, 5],
    )[0]

    # Type-specific properties
    if txn_type == "atm":
        amount = round(rng.uniform(60, 3000), 2)
        merchant = rng.choice(ATM_MERCHANTS)
        card_present = True
        entry_mode = "chip"
        pin_verified = True
        card_network = None  # ATM withdrawals don't go through card networks for disputes

    elif txn_type == "debit_card_pos":
        amount = round(rng.uniform(25, 8000), 2)
        merchant = rng.choice(POS_MERCHANTS)
        card_present = rng.random() < 0.7
        entry_mode = rng.choice(["chip", "swipe", "contactless", "keyed"])
        pin_verified = rng.random() < 0.5
        card_network = rng.choice(CARD_NETWORKS)

    elif txn_type == "ach":
        amount = round(rng.uniform(100, 15000), 2)
        merchant = rng.choice(ACH_MERCHANTS)
        card_present = False
        entry_mode = "online"
        pin_verified = False
        card_network = None

    elif txn_type == "p2p":
        amount = round(rng.uniform(50, 5000), 2)
        merchant = rng.choice(P2P_MERCHANTS)
        card_present = False
        entry_mode = "online"
        pin_verified = False
        card_network = None

    elif txn_type == "wire":
        amount = round(rng.uniform(1000, 50000), 2)
        merchant = rng.choice(WIRE_MERCHANTS)
        card_present = False
        entry_mode = "online"
        pin_verified = False
        card_network = None

    else:  # bill_pay
        amount = round(rng.uniform(50, 3000), 2)
        merchant = rng.choice(BILL_PAY_MERCHANTS)
        card_present = False
        entry_mode = "online"
        pin_verified = False
        card_network = None

    # Out of state: 15% chance, computed against account_state if provided
    is_out_of_state = rng.random() < 0.15
    if account_state:
        if is_out_of_state:
            other_states = [s for s in US_STATES if s != account_state]
            merchant_state = rng.choice(other_states)
        else:
            merchant_state = account_state
    else:
        merchant_state = rng.choice(US_STATES)

    # Transaction date: 1-14 days before today
    days_ago = rng.randint(1, 14)
    txn_date = (date.today() - timedelta(days=days_ago)).isoformat()

    # Deterministic transaction ID
    txn_id_suffix = rng.randint(100000, 999999)
    transaction_id = f"TXN-{txn_date.replace('-', '')}-{txn_id_suffix}"

    return {
        "complaint_id": complaint_id,
        "transaction_id": transaction_id,
        "transaction_date": txn_date,
        "transaction_amount": amount,
        "transaction_type": txn_type,
        "merchant_name": merchant,
        "merchant_state": merchant_state,
        "merchant_category_code": _mcc_for_type(txn_type),
        "is_pos_debit": txn_type == "debit_card_pos",
        "is_atm": txn_type == "atm",
        "is_ach": txn_type == "ach",
        "is_p2p": txn_type == "p2p",
        "is_out_of_state": is_out_of_state,
        "card_present": card_present,
        "card_network": card_network,
        "terminal_type": _terminal_for_type(txn_type),
        "entry_mode": entry_mode,
        "pin_verified": pin_verified,
        "auth_amount": amount,
        "auth_response": "approved",
        "posted_date": txn_date,
        "status": "posted",
    }


def _mcc_for_type(txn_type: str) -> str:
    """Merchant Category Code for transaction type."""
    return {
        "atm": "6011",
        "debit_card_pos": "5999",
        "ach": "0000",
        "p2p": "6012",
        "wire": "6051",
        "bill_pay": "4900",
    }.get(txn_type, "5999")


def _terminal_for_type(txn_type: str) -> str:
    return {
        "atm": "atm",
        "debit_card_pos": "pos",
        "ach": "ach_network",
        "p2p": "p2p_app",
        "wire": "wire_network",
        "bill_pay": "online",
    }.get(txn_type, "pos")


# ─── HOLIDAY CALENDAR ──────────────────────────────────────────────────────

FED_HOLIDAYS_2026 = [
    {"date": "2026-01-01", "name": "New Year's Day"},
    {"date": "2026-01-19", "name": "Birthday of Martin Luther King, Jr."},
    {"date": "2026-02-16", "name": "Washington's Birthday"},
    {"date": "2026-05-25", "name": "Memorial Day"},
    {"date": "2026-06-19", "name": "Juneteenth National Independence Day"},
    {"date": "2026-07-03", "name": "Independence Day (observed)"},
    {"date": "2026-09-07", "name": "Labor Day"},
    {"date": "2026-10-12", "name": "Columbus Day"},
    {"date": "2026-11-11", "name": "Veterans Day"},
    {"date": "2026-11-26", "name": "Thanksgiving Day"},
    {"date": "2026-12-25", "name": "Christmas Day"},
]


def get_holiday_calendar(year: int = 2026) -> dict:
    """Return the Federal Reserve holiday calendar for a given year."""
    return {
        "year": year,
        "institution": "default",
        "calendar_type": "federal_reserve",
        "holidays": FED_HOLIDAYS_2026 if year == 2026 else [],
    }
