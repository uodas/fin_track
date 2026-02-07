from src.schemas import TransactionSchema
import hashlib
import sqlite3
import yaml
import logging
import pandas as pd
from decimal import Decimal
from pathlib import Path
from src.config import DB_PATH, INPUT_FOLDER, CONFIG_FILE

logger = logging.getLogger(__name__)


def read_config() -> dict:
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        logger.warning("config.yaml not found. Returning empty dict.")
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def identify_bank_type(file_path: Path) -> str:
    """
    Identifies the bank type for a file based on its content headers.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            # Read first few lines for better identification
            lines = [f.readline() for _ in range(5)]
            content = "".join(lines)

            if '"Booking Date"' in content and '"Value Date"' in content:
                return "n26"
            elif "SĄSKAITOS" in content or "SUMA SĄSKAITOS VALIUTA" in content:
                return "seb"
            elif (
                "Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance"
                in content
            ):
                return "revolut"
    except Exception as e:
        logger.error(f"Error identifying bank type for {file_path}: {e}")
    return "unknown"


def get_available_files(input_dir: str) -> dict[str, list[Path]]:
    """
    Scans the input directory and identifies the bank type for each file.
    Returns a mapping of bank_type -> list of Paths.
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        logger.warning(f"Input directory {input_dir} does not exist.")
        return {}

    banks_files = {}
    for file in input_path.glob("*.csv"):
        bank_type = identify_bank_type(file)
        if bank_type != "unknown":
            banks_files.setdefault(bank_type, []).append(file)
        else:
            logger.info(f"Skipping unknown file: {file}")

    return banks_files


def generate_hash_id(row: pd.Series) -> str:
    """
    Generates a unique hash ID for a transaction row based on its date, amount, and description.
    """
    raw_str = f"{row['date']}{row['amount']}{row['description']}"
    return hashlib.md5(raw_str.encode()).hexdigest()


def _normalize_df(df: pd.DataFrame, rename_map: dict, drop_cols: list) -> pd.DataFrame:
    """Helper to clean and normalize DataFrames."""
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    df = df.rename(columns=rename_map)
    return df


def parse_n26_file(file_path: Path) -> pd.DataFrame:
    """Parses an N26 bank statement CSV file."""
    df = pd.read_csv(file_path, sep=",", dtype={"Amount (EUR)": str})

    rename_map = {
        "Value Date": "date",
        "Amount (EUR)": "amount",
        "Partner Name": "description",
        "Payment Reference": "note",
    }
    drop_cols = [
        "Booking Date",
        "Partner Iban",
        "Type",
        "Account Name",
        "Original Amount",
        "Original Currency",
        "Exchange Rate",
    ]

    df = _normalize_df(df, rename_map, drop_cols)
    df["amount"] = df["amount"].str.replace(",", "").apply(Decimal)

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["hash_id"] = df.apply(generate_hash_id, axis=1)

    df = TransactionSchema.validate(df)
    return df


def parse_seb_file(file_path: Path) -> pd.DataFrame:
    """Parses a SEB bank statement CSV file."""
    df = pd.read_csv(
        file_path,
        sep=";",
        skiprows=1,
        decimal=",",
        dtype={"SUMA SĄSKAITOS VALIUTA": str},
    )

    rename_map = {
        "DATA": "date",
        "MOKĖTOJO ARBA GAVĖJO PAVADINIMAS": "description",
        "MOKĖJIMO PASKIRTIS": "note",
        "SUMA SĄSKAITOS VALIUTA": "amount",
    }
    drop_cols = [
        "DOK NR.",
        "MOKĖTOJO ARBA GAVĖJO IDENTIFIKACINIS KODAS",
        "SUMA",
        "SĄSKAITA",
        "DOKUMENTO DATA",
        "TRANSAKCIJOS TIPAS",
        "TRANSAKCIJOS KODAS",
        "KREDITO ĮSTAIGOS SWIFT KODAS",
        "KREDITO ĮSTAIGOS PAVADINIMAS",
        "NUORODA",
        "SĄSKAITOS NR",
        "SĄSKAITOS VALIUTA",
        "Unnamed: 18",
    ]

    df = _normalize_df(df, rename_map, drop_cols)
    df["amount"] = df["amount"].str.replace(",", ".").apply(Decimal)

    if "VALIUTA" in df.columns:
        df["note"] = df["note"].astype(str) + "; " + df["VALIUTA"].astype(str)
        df = df.drop(columns=["VALIUTA"])

    if "DEBETAS/KREDITAS" in df.columns:
        df["amount"] = df.apply(
            lambda row: -row["amount"]
            if row["DEBETAS/KREDITAS"] == "D"
            else row["amount"],
            axis=1,
        )
        df = df.drop(columns=["DEBETAS/KREDITAS"])

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["hash_id"] = df.apply(generate_hash_id, axis=1)
    df = TransactionSchema.validate(df)
    return df


def parse_revolut_file(file_path: Path) -> pd.DataFrame:
    """Parses a Revolut bank statement CSV file."""
    df = pd.read_csv(file_path, sep=",", dtype={"Amount": str})
    df = df[df["State"] == "COMPLETED"].copy()

    rename_map = {
        "Completed Date": "date",
        "Description": "description",
        "Amount": "amount",
        "Currency": "note",
    }
    drop_cols = ["Type", "Product", "Started Date", "Fee", "State", "Balance"]

    df = _normalize_df(df, rename_map, drop_cols)
    df["amount"] = df["amount"].str.replace(",", "").apply(Decimal)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["hash_id"] = df.apply(generate_hash_id, axis=1)
    df = TransactionSchema.validate(df)
    return df


def filter_our_present_data(df: pd.DataFrame) -> pd.DataFrame:
    """Filters out transactions already present in the database."""
    if df.empty:
        return df

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hash_id FROM transactions")
        existing_hash_ids = {row[0] for row in cursor.fetchall()}

    return df[~df["hash_id"].isin(existing_hash_ids)].copy()


def read_statement_files(config: dict) -> dict[str, pd.DataFrame]:
    """Reads, parses, and filters new transactions from all available files."""
    banks_files = get_available_files(INPUT_FOLDER)

    parser_map = {
        "n26": parse_n26_file,
        "seb": parse_seb_file,
        "revolut": parse_revolut_file,
    }

    results = {}
    for bank_type, file_paths in banks_files.items():
        parse_func = parser_map.get(bank_type)
        if not parse_func:
            continue

        dfs = []
        for path in file_paths:
            try:
                dfs.append(parse_func(path))
            except Exception as e:
                logger.error(f"Failed to parse {path} as {bank_type}: {e}")

        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            results[bank_type] = filter_our_present_data(combined_df)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.config import INPUT_FOLDER

    # Test identification
    files = get_available_files(INPUT_FOLDER)
    print(f"Identified files: {files}")

    # Test full flow
    statements = read_statement_files({})
    for bank, df in statements.items():
        print(f"\n--- {bank} ({len(df)} new transactions) ---")
        if not df.empty:
            print(df.head())
