from src import db, parsers, categorizer, sheets
from src.config import LOG_PATH
import logging
import sys


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    # read config
    config = parsers.read_config()

    # initialize database
    db.initialize_database(config)

    # read statement files
    bank_statements = parsers.read_statement_files(config)

    # categorize transaction categories
    income_cats = config.get("categories", {}).get("income", {})
    expense_cats = config.get("categories", {}).get("expense", {})
    categories = categorizer.load_categories(income_cats, expense_cats)
    predict_category = categorizer.SmartCategorizer(categories=categories)

    # load data into database
    for bank, df in bank_statements.items():
        df = predict_category.categorize_transactions(df)
        db.load_data(bank, df)

    # upload to google sheet
    df = db.get_all_transactions()
    sheets.upload_to_sheet(
        df, config["google_sheet"]["file_name"], config["google_sheet"]["tab_name"]
    )


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting application...")
    try:
        main()
    except Exception as e:
        logger.error(f"Application failed with error: {e}")
    finally:
        logger.info("Application finished.")
