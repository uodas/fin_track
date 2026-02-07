# FinTrack: Intelligent Bank Statement Categorizer

FinTrack is a Python-based tool designed to automate the parsing, categorization, and storage of financial transactions from various bank statements. 

## 🚀 Features

-   **Multi-Bank Support**: Automatically detects and parses CSV statements from several banks.
-   **Smart Categorization**: Uses NLP (Semantic Similarity) to categorize transactions, even with messy descriptions.
-   **Batch Processing**: Efficiently handles multiple statement files simultaneously using batched ML encoding.
-   **Robust Storage**: Stores all transactions in a local SQLite database with unique IDs to prevent duplicates.
-   **Centralized Config**: Easy management of categories, accounts, and application settings via `config.yaml` and `.env`.
-   **Clean & Modern**: Built with `pathlib`, `pydantic`, and modern Python practices.

## 📁 Project Structure

```text
fin_track/
├── src/
│   ├── config.py       # Configuration and settings management
│   ├── parsers.py      # Bank-specific CSV parsing logic
│   ├── categorizer.py  # NLP-based smart categorization
│   └── db.py           # SQLite database interactions
├── input/              # Drop your CSV statement files here
├── database/           # Where the SQLite DB is stored
├── main.py             # Main entry point
├── config.yaml         # Category and account definitions
└── pyproject.toml      # Project dependencies
```

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd fin_track
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r pyproject.toml
    ```

## ⚙️ Configuration

### 1. `config.yaml`
Define your spending categories and bank accounts in `config.yaml`:
```yaml
categories:
  income:
    Salary: "Income from my job"
  expense:
    Food: "Groceries, restaurants, and cafes"
    Rent: "Housing and apartment rent"

accounts:
  bank1: "My main bank account"
  bank2: "My secondary bank account"
```

### 2. Environment Variables
Create a `.env` file for sensitive or environment-specific settings:
```env
DEBUG_MODE=False
DATABASE_NAME=finance.db
```

## 📖 Usage

1.  **Export Statements**: Download your CSV statements from your bank.
2.  **Import**: Place the CSV files into the `input/` folder.
3.  **Run**:
    ```bash
    python main.py
    ```
4.  **View Results**: The script will parse the files, categorize the data, and load it into the database located in the `database/` folder.

## 🧪 Running Tests

The project includes a comprehensive test suite using `pytest`.
```bash
python -m pytest tests/
```