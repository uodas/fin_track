import torch
import logging
from dataclasses import dataclass
import re
import pandas as pd
from rapidfuzz import process, fuzz
from sentence_transformers import SentenceTransformer, util
from src.config import MODEL_NAME, MODEL_CACHE

logger = logging.getLogger(__name__)


@dataclass
class CategoryData:
    name: str
    description: str
    keywords: list[str]
    category_type: str
    description_embedding: torch.Tensor = None


def load_categories(
    income_categories: dict, expense_categories: dict
) -> list[CategoryData]:
    categories = []

    for name, data in income_categories.items():
        categories.append(
            CategoryData(
                name=name,
                description=data.get("description", ""),
                keywords=data.get("keywords", []),
                category_type=data.get("category_type", "income"),
            )
        )

    for name, data in expense_categories.items():
        categories.append(
            CategoryData(
                name=name,
                description=data.get("description", ""),
                keywords=data.get("keywords", []),
                category_type=data.get("category_type", "expense"),
            )
        )
    return categories


class SmartCategorizer:
    def __init__(
        self,
        categories: list[CategoryData],
        model_name: str = MODEL_NAME,
        cache_folder: str = MODEL_CACHE,
    ):
        """
        Initializes the categorizer with a list of CategoryData.
        """
        logger.info(
            f"Loading categorization model '{model_name}'... (this may take a moment)"
        )

        # This will download the model to cache_folder only on the first run
        self.model = SentenceTransformer(model_name, cache_folder=cache_folder)

        if not categories:
            raise ValueError("No categories provided to SmartCategorizer!")

        self.categories = categories

        # Pre-compute the embeddings for the categories once
        self.category_names = [cat.name for cat in categories]
        self.category_descriptions = [cat.description for cat in categories]

        # Build keyword mappings
        self.keyword_to_category = {}
        self.all_keywords = []

        for cat in categories:
            for kw in cat.keywords:
                kw_lower = kw.lower()
                self.keyword_to_category[kw_lower] = cat.name
                self.all_keywords.append(kw_lower)

        # Batch encode all descriptions
        self.category_embeddings = self.model.encode(
            self.category_descriptions, convert_to_tensor=True
        )

    def find_fuzzy_match(self, description: str, threshold: float = 90.0) -> str | None:
        """
        Tries to find a fuzzy match for the description in the keywords.
        """
        if not self.all_keywords:
            return None

        cleaned_description = description.lower()

        result = process.extractOne(
            cleaned_description,
            self.all_keywords,
            scorer=fuzz.partial_ratio,
            score_cutoff=threshold,
        )

        if result:
            matched_kw, score, index = result
            return self.keyword_to_category[matched_kw]

        return None

    def predict_batch(
        self,
        descriptions: list[str],
        threshold: float = 0.25,
        fuzzy_threshold: float = 90.0,
    ) -> list[str]:
        """
        Predicts categories for a list of descriptions.
        Tries fuzzy matching first, then falls back to the model.
        """
        if not descriptions:
            return []

        results = [None] * len(descriptions)
        remaining_indices = []
        remaining_descriptions = []

        # Clean descriptions once for both fuzzy and model matching
        cleaned_descriptions = [d.strip() for d in descriptions]

        # 1. Try fuzzy matching first
        for i, desc in enumerate(cleaned_descriptions):
            fuzzy_cat = self.find_fuzzy_match(desc, threshold=fuzzy_threshold)
            if fuzzy_cat:
                results[i] = fuzzy_cat
            else:
                remaining_indices.append(i)
                remaining_descriptions.append(desc)

        # 2. Model fallback for remaining
        if remaining_descriptions:
            desc_embeddings = self.model.encode(
                remaining_descriptions, convert_to_tensor=True
            )
            cosine_scores = util.cos_sim(desc_embeddings, self.category_embeddings)

            for i, res_idx in enumerate(remaining_indices):
                scores = cosine_scores[i]
                best_score_idx = torch.argmax(scores).item()
                best_score = scores[best_score_idx].item()

                if best_score > threshold:
                    results[res_idx] = self.category_names[best_score_idx]
                else:
                    results[res_idx] = "Unknown"

        return results

    def predict(self, description: str, threshold: float = 0.25) -> str:
        """
        Returns the best category name or 'Unknown' if confidence is low.
        Use predict_batch for multiple descriptions.
        """
        return self.predict_batch([description], threshold)[0]

    def categorize_transactions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Categorizes transactions in the DataFrame using batch encoding for performance.
        """
        if df.empty:
            df["category"] = []
            return df

        # Create search strings
        search_strings = (
            df["description"].fillna("")
            + " "
            + df["note"].fillna("")
            + " amount="
            + (df["amount"].astype(str))
        ).tolist()

        # Batch prediction
        df["category"] = self.predict_batch(search_strings)

        return df


if __name__ == "__main__":
    from src.parsers import (
        read_config,
        parse_n26_file,
    )

    config = read_config()

    categories = load_categories(
        config.get("categories", {}).get("income", {}),
        config.get("categories", {}).get("expense", {}),
    )

    cat = SmartCategorizer(categories=categories)

    # Use a dummy dataframe for testing if file doesn't exist
    try:
        test_data = parse_n26_file("input/n26_nov.csv")
    except Exception:
        test_data = pd.DataFrame(
            {
                "description": [
                    "THERMO FISHER SCIENTIFIC BALTICS UAB",
                    "Rimi Vilnius",
                    "Bolt ride",
                ],
                "note": ["Salary", "Groceries", "Taxi"],
                "amount": [3000.0, -15.50, -5.00],
                "date": ["2023-11-01", "2023-11-02", "2023-11-03"],
            }
        )

    df = cat.categorize_transactions(test_data)
    print(df.to_string())
