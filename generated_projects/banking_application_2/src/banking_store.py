import json
from datetime import datetime
from pathlib import Path


DATA_FILE = Path("data") / "banking_data.json"


def default_data() -> dict:
    return {
        "customers": [
            {"id": "CUST-1001", "name": "Asha Patel", "email": "asha@example.com"},
            {"id": "CUST-1002", "name": "Rahul Sharma", "email": "rahul@example.com"},
        ],
        "accounts": [
            {"account_no": "AC-90001", "customer_id": "CUST-1001", "type": "Savings", "balance": 125000.0},
            {"account_no": "AC-90002", "customer_id": "CUST-1002", "type": "Current", "balance": 68000.0},
        ],
        "transactions": [
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account_no": "AC-90001",
                "kind": "deposit",
                "amount": 25000.0,
                "note": "Opening deposit",
            }
        ],
    }


def load_data() -> dict:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        save_data(default_data())
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_account(data: dict, account_no: str) -> dict | None:
    return next((account for account in data["accounts"] if account["account_no"] == account_no), None)


def record_transaction(data: dict, account_no: str, kind: str, amount: float, note: str) -> None:
    data["transactions"].append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account_no": account_no,
            "kind": kind,
            "amount": amount,
            "note": note,
        }
    )
