import pytest
import torch
from unittest.mock import patch, MagicMock
from src.categorizer import SmartCategorizer, CategoryData


@pytest.fixture
def mock_categorizer():
    with patch("src.categorizer.SentenceTransformer") as mock_st:
        # Mock categories as CategoryData list
        categories = [
            CategoryData(
                name="Salary",
                description="Paycheck",
                keywords=["Salary", "Pay"],
                category_type="income",
            ),
            CategoryData(
                name="Food",
                description="Groceries",
                keywords=["Rimi", "Maxima"],
                category_type="expense",
            ),
            CategoryData(
                name="Transport",
                description="Bus and taxi",
                keywords=["Bolt", "Uber"],
                category_type="expense",
            ),
        ]

        # Mock SentenceTransformer
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        # Mock encode to return dummy embeddings
        # Since categories are encoded in __init__, we need to match the indices
        mock_model.encode.return_value = torch.tensor(
            [
                [1.0, 0.0],  # Salary
                [0.0, 1.0],  # Food
                [0.5, 0.5],  # Transport
            ]
        )

        categorizer = SmartCategorizer(categories=categories)
        yield categorizer, mock_model


def test_predict_high_confidence(mock_categorizer):
    categorizer, mock_model = mock_categorizer

    # Mock encode for query to be similar to 'Food' [0, 1]
    mock_model.encode.return_value = torch.tensor([0.1, 0.9])

    category = categorizer.predict("Buying some bread")
    assert category == "Food"


def test_predict_low_confidence(mock_categorizer):
    categorizer, mock_model = mock_categorizer

    # Mock encode for query to be far from everything
    mock_model.encode.return_value = torch.tensor([-1.0, -1.0])

    category = categorizer.predict("Something completely different", threshold=0.9)
    assert category == "Unknown"
