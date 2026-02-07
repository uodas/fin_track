import logging
import sqlite3
import pandas as pd
from src.config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Returns a connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    # Crucial: SQLite does not enforce Foreign Keys by default!
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_all_categories() -> list[dict]:
    """Returns all categories as a list of dictionaries."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM categories")
        rows = c.fetchall()
        return [dict(row) for row in rows]


def get_all_transactions() -> pd.DataFrame:
    """Returns all transactions as a list of dictionaries."""

    query = """SELECT 
        t.hash_id,
        t.date, 
        t.amount, 
        t.description,
        t.note, 
        c.name as category,
        a.name as account
    FROM transactions t
    LEFT JOIN categories c ON t.category_id = c.id
    LEFT JOIN accounts a ON t.account_id = a.id
    ORDER BY t.date DESC
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def load_data(bank: str, data: pd.DataFrame) -> None:
    """Loads transaction data from a DataFrame into the database."""
    if data.empty:
        logger.info(f"No new data to load for {bank}.")
        return

    with get_connection() as conn:
        c = conn.cursor()

        # Get account ID (case-insensitive)
        c.execute("SELECT id FROM accounts WHERE name = ? COLLATE NOCASE", (bank,))
        account_row = c.fetchone()
        if not account_row:
            raise ValueError(f"Account '{bank}' not found in database.")
        account_id = account_row[0]

        # Get category mapping {name: id}
        c.execute("SELECT id, name FROM categories")
        category_map = {name: cid for cid, name in c.fetchall()}

        # Prepare records for insertion
        records = []
        for _, row in data.iterrows():
            category_name = row.get("category", "Unknown")
            category_id = category_map.get(category_name)

            if category_id is None:
                logger.warning(
                    f"Category '{category_name}' not found. Using 'Unknown'."
                )
                category_id = category_map.get("Unknown")

            # Convert amount to cents (integer)
            amount_cents = int(row["amount"] * 100)

            records.append(
                (
                    row["hash_id"],
                    row["date"],
                    amount_cents,
                    row["description"],
                    account_id,
                    category_id,
                    row["note"],
                )
            )

        # Batched insert for performance
        c.executemany(
            """
            INSERT OR IGNORE INTO transactions (
                hash_id, date, amount, description, account_id, category_id, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        logger.info(f"Successfully processed {len(records)} transactions for {bank}.")


def _seed_default_data(c: sqlite3.Cursor, config: dict) -> None:
    """Seeds default categories and accounts from config."""
    # Seed Categories
    c.execute("SELECT count(*) FROM categories")
    if c.fetchone()[0] == 0:
        logger.info("Seeding default categories from config...")
        categories = config.get("categories", {})

        for cat_type, cats in [
            ("Income", categories.get("income", {})),
            ("Expense", categories.get("expense", {})),
        ]:
            for name, data in cats.items():
                desc = data.get("description", "")
                keywords = ",".join(data.get("keywords", []))
                c.execute(
                    "INSERT OR IGNORE INTO categories (name, type, keywords, description) VALUES (?, ?, ?, ?)",
                    (name, cat_type, keywords, desc),
                )

        # Ensure 'Unknown' category exists
        c.execute(
            "INSERT OR IGNORE INTO categories (name, type, keywords, description) VALUES (?, ?, ?, ?)",
            (
                "Unknown",
                "Expense",
                "",
                "Automatically assigned for low confidence matches",
            ),
        )

    # Seed Accounts
    c.execute("SELECT count(*) FROM accounts")
    if c.fetchone()[0] == 0:
        logger.info("Seeding default accounts from config...")
        accounts = config.get("accounts", {})
        for name, desc in accounts.items():
            c.execute(
                "INSERT OR IGNORE INTO accounts (name, description) VALUES (?, ?)",
                (name, desc),
            )


def initialize_database(config: dict) -> None:
    """Creates tables and seeds default data."""
    with get_connection() as conn:
        c = conn.cursor()

        # 1. Accounts Table
        c.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL
            )
        """)

        # 2. Categories Table
        c.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT CHECK(type IN ('Income', 'Expense')), 
                keywords TEXT NOT NULL,
                description TEXT NOT NULL
            )
        """)

        # 3. Transactions Table
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                hash_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                account_id INTEGER,
                category_id INTEGER,
                note TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        """)

        _seed_default_data(c, config)


if __name__ == "__main__":
    df = get_all_transactions()
    print(df)
