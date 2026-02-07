import gspread
import logging
from gspread_dataframe import set_with_dataframe
import pandas as pd
from src.config import GOOGLE_SERVICE_ACCOUNT
import os

logger = logging.getLogger(__name__)

# Define the scope - what the bot is allowed to do
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client():
    """Authenticates and returns the gspread client."""
    # It looks for 'service_account.json' in your root folder
    # You can also point to a specific path if you prefer
    return gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT)


def upload_to_sheet(df: pd.DataFrame, sheet_name: str, tab_name: str = "Raw_Data"):
    """
    Clears the target tab and uploads the new DataFrame.

    :param df: The Pandas DataFrame to upload
    :param sheet_name: The name of your Google Sheet file (e.g., "My Finances")
    :param tab_name: The specific tab to update (defaults to "Raw_Data")
    """
    logger.info(f"Connecting to Google Sheets: '{sheet_name}'...")
    client = get_client()

    try:
        # Open the spreadsheet
        sh = client.open(sheet_name)

        # Select the worksheet (tab) or create it if it doesn't exist
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            logger.info(f"Tab '{tab_name}' not found. Creating it...")
            worksheet = sh.add_worksheet(title=tab_name, rows=1000, cols=20)

        # CLEAR existing data to avoid mixing old and new
        worksheet.clear()

        df["amount"] = df["amount"] / 100.0
        # UPLOAD new data
        # set_with_dataframe handles headers and NaN values automatically
        set_with_dataframe(worksheet, df, include_column_header=True)

        logger.info("Upload successful!")

    except Exception as e:
        logger.error(f"Error uploading to Google Sheets: {e}")


# --- Test Block ---
if __name__ == "__main__":
    from src.parsers import read_config

    config = read_config()["google_sheet"]

    # Create a dummy dataframe to test
    data = {
        "Date": ["2025-01-01", "2025-01-02"],
        "Amount": [100.50, -25.00],
        "Category": ["Salary", "Lunch"],
    }
    df_test = pd.DataFrame(data)

    # Replace 'My Finance Tracker' with the EXACT name of your Google Sheet
    upload_to_sheet(df_test, config["file_name"], config["tab_name"])
