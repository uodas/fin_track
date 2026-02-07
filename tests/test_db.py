import sqlite3
import pytest
import pandas as pd
from unittest.mock import patch
from src import db


@pytest.fixture
def mock_db_path(tmp_path):
    # Create a temporary database file
    db_file = tmp_path / "test_finance.db"
    with patch("src.db.DB_PATH", str(db_file)):
        yield str(db_file)


def test_initialize_database(mock_db_path):
    config = {
        "categories": {
            "income": {
                "Salary": {"description": "Monthly pay", "keywords": ["Salary"]}
            },
            "expense": {"Food": {"description": "Groceries", "keywords": ["Food"]}},
        },
        "accounts": {"SEB": "Main account"},
    }
    db.initialize_database(config)

    conn = sqlite3.connect(mock_db_path)
    c = conn.cursor()

    # Check tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    assert "accounts" in tables
    assert "categories" in tables
    assert "transactions" in tables

    # Check seeded data
    c.execute("SELECT name FROM categories WHERE type='Income'")
    assert c.fetchone()[0] == "Salary"

    c.execute("SELECT name FROM accounts")
    assert c.fetchone()[0] == "SEB"

    conn.close()


def test_get_all_categories(mock_db_path):
    config = {
        "categories": {
            "income": {"Salary": {"description": "Pay", "keywords": ["Sal"]}},
            "expense": {},
        },
        "accounts": {},
    }
    db.initialize_database(config)

    categories = db.get_all_categories()
    # Salary + Unknown
    assert len(categories) == 2
    assert any(c["name"] == "Salary" for c in categories)
    assert any(c["name"] == "Unknown" for c in categories)


def test_load_data(mock_db_path):
    config = {
        "categories": {
            "income": {},
            "expense": {"Food": {"description": "Groceries", "keywords": ["Food"]}},
        },
        "accounts": {"SEB": "Main account"},
    }
    db.initialize_database(config)

    data = pd.DataFrame(
        {
            "hash_id": ["abc123"],
            "date": ["2023-11-01"],
            "amount": [10.50],  # Will be converted to int (1050)
            "description": ["Lunch"],
            "category": ["Food"],
            "note": ["Tasty"],
        }
    )

    db.load_data("SEB", data)

    conn = sqlite3.connect(mock_db_path)
    c = conn.cursor()

    # Get IDs for verification
    c.execute("SELECT id FROM categories WHERE name = 'Food'")
    food_id = c.fetchone()[0]
    c.execute("SELECT id FROM accounts WHERE name = 'SEB'")
    account_id = c.fetchone()[0]

    c.execute("SELECT amount, category_id, account_id FROM transactions")
    row = c.fetchone()
    assert row[0] == 1050
    assert row[1] == food_id
    assert row[2] == account_id
    conn.close()


def test_load_data_invalid_account(mock_db_path):
    config = {"categories": {"income": {}, "expense": {}}, "accounts": {}}
    db.initialize_database(config)

    data = pd.DataFrame([{"hash_id": "1", "amount": 1, "category": "Food"}])
    with pytest.raises(ValueError, match="Account 'Unknown' not found in database"):
        db.load_data("Unknown", data)
