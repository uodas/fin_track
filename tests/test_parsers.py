import pandas as pd
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from src import parsers


def test_generate_hash_id():
    row = pd.Series(
        {
            "date": "2023-11-01",
            "amount": Decimal("10.50"),
            "description": "Test Transaction",
        }
    )
    hash_id = parsers.generate_hash_id(row)
    assert isinstance(hash_id, str)
    assert len(hash_id) == 32  # MD5 is 32 chars

    # Test consistency
    assert parsers.generate_hash_id(row) == hash_id


def test_get_available_files():
    mock_files = [
        Path("fake_dir/n26.csv"),
        Path("fake_dir/seb.csv"),
        Path("fake_dir/revolut.csv"),
        Path("fake_dir/unknown.csv"),
    ]

    with (
        patch("src.parsers.Path.exists", return_value=True),
        patch("src.parsers.Path.glob", return_value=mock_files),
        patch("src.parsers.identify_bank_type") as mock_identify,
    ):
        mock_identify.side_effect = lambda p: (
            "n26"
            if "n26" in p.name
            else "seb"
            if "seb" in p.name
            else "revolut"
            if "revolut" in p.name
            else "unknown"
        )

        files = parsers.get_available_files("fake_dir")

        assert "n26" in files
        assert Path("fake_dir/n26.csv") in files["n26"]
        assert "seb" in files
        assert Path("fake_dir/seb.csv") in files["seb"]
        assert "revolut" in files
        assert Path("fake_dir/revolut.csv") in files["revolut"]
        assert "unknown" not in files  # Unknown files are logged and skipped


@patch("pandas.read_csv")
def test_parse_n26_file(mock_read_csv):
    # Mock N26 CSV data
    data = {
        "Booking Date": ["2023-11-01"],
        "Value Date": ["2023-11-01"],
        "Partner Name": ["Store A"],
        "Partner Iban": ["IBAN1"],
        "Type": ["Card"],
        "Payment Reference": ["Ref"],
        "Account Name": ["Main"],
        "Amount (EUR)": ["-10.50"],
        "Original Amount": ["-10.50"],
        "Original Currency": ["EUR"],
        "Exchange Rate": ["1.0"],
    }
    mock_read_csv.return_value = pd.DataFrame(data)

    df = parsers.parse_n26_file("fake_n26.csv")

    assert "date" in df.columns
    assert "amount" in df.columns
    assert "description" in df.columns
    assert "note" in df.columns
    assert "hash_id" in df.columns
    assert isinstance(df.iloc[0]["amount"], Decimal)
    assert df.iloc[0]["description"] == "Store A"


@patch("pandas.read_csv")
def test_parse_seb_file(mock_read_csv):
    # Mock SEB CSV data - skipping columns check, focusing on renaming and conversion
    data = {
        "DATA": ["2023-11-01"],
        "MOKĖTOJO ARBA GAVĖJO PAVADINIMAS": ["Store B"],
        "MOKĖJIMO PASKIRTIS": ["Coffee"],
        "SUMA SĄSKAITOS VALIUTA": ["-5,50"],
        "VALIUTA": ["EUR"],
        "DEBETAS/KREDITAS": ["K"],
        # Added missing columns that are dropped in the function
        "DOK NR.": ["1"],
        "MOKĖTOJO ARBA GAVĖJO IDENTIFIKACINIS KODAS": ["2"],
        "SUMA": ["-5,50"],
        "SĄSKAITA": ["3"],
        "DOKUMENTO DATA": ["4"],
        "TRANSAKCIJOS TIPAS": ["5"],
        "TRANSAKCIJOS KODAS": ["6"],
        "KREDITO ĮSTAIGOS SWIFT KODAS": ["7"],
        "KREDITO ĮSTAIGOS PAVADINIMAS": ["8"],
        "NUORODA": ["9"],
        "SĄSKAITOS NR": ["10"],
        "SĄSKAITOS VALIUTA": ["11"],
        "Unnamed: 18": ["12"],
    }
    mock_read_csv.return_value = pd.DataFrame(data)

    df = parsers.parse_seb_file("fake_seb.csv")
    assert df.iloc[0]["amount"] == Decimal("-5.50")
    assert df.iloc[0]["description"] == "Store B"
    assert "Coffee" in df.iloc[0]["note"]


@patch("pandas.read_csv")
def test_parse_revolut_file(mock_read_csv):
    data = {
        "Type": ["CARD_PAYMENT", "TOPUP"],
        "Product": ["Current", "Current"],
        "Started Date": ["2023-11-01 10:00:00", "2023-11-01 11:00:00"],
        "Completed Date": ["2023-11-01 10:05:00", "2023-11-01 11:05:00"],
        "Description": ["Netflix", "Transfer"],
        "Amount": ["-12.99", "100.00"],
        "Fee": ["0", "0"],
        "Currency": ["EUR", "EUR"],
        "State": ["COMPLETED", "PENDING"],
        "Balance": ["1000", "1100"],
    }
    mock_read_csv.return_value = pd.DataFrame(data)

    df = parsers.parse_revolut_file("fake_revolut.csv")

    # Only COMPLETED should be present
    assert len(df) == 1
    assert df.iloc[0]["description"] == "Netflix"
    assert df.iloc[0]["amount"] == Decimal("-12.99")
