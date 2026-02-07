import sys
import os
import pandas as pd
from pathlib import Path

# Add src to sys.path
sys.path.append(os.getcwd())

from src.categorizer import SmartCategorizer, load_categories


def test_fuzzy_matching():
    mock_categories = {
        "Food": {
            "keywords": ["RIMI", "MAXIMA", "IKI"],
            "description": "Groceries and food",
        },
        "Transport": {
            "keywords": ["Bolt", "Uber", "Taxi"],
            "description": "Transport expenses",
        },
    }
    categories = load_categories({}, mock_categories)

    # Initialize categorizer
    cat = SmartCategorizer(categories=categories)

    # Test cases
    test_cases = [
        ("RIMI VILNIUS", "Food"),  # Exact keyword in string
        ("Rimi", "Food"),  # Case insensitive
        ("BOLT.EU/O/123", "Transport"),  # Substring match
        ("MAXIMA XXX", "Food"),  # Substring
        ("Taxis", "Transport"),  # Fuzzy match (ratio)
        (
            "Something completely different",
            "Unknown",
        ),  # Fallback (assuming model doesn't match highly)
    ]

    print("\nRunning Fuzzy Matching Tests:")
    all_passed = True
    for desc, expected in test_cases:
        prediction = cat.predict(desc)
        status = "PASSED" if prediction == expected else f"FAILED (Got: {prediction})"
        print(
            f"Desc: '{desc}' -> Expected: '{expected}', Got: '{prediction}' [{status}]"
        )
        if prediction != expected:
            all_passed = False

    if all_passed:
        print("\nAll fuzzy matching tests PASSED!")
    else:
        print("\nSome tests FAILED.")


if __name__ == "__main__":
    try:
        test_fuzzy_matching()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()
