"""
tests/test_tools.py

Offline tests for the three FitFindr tools.
LLM-dependent paths (suggest_outfit, create_fit_card happy path) are
verified manually via the Milestone 5 one-liners.
"""

import sys
import os

# Ensure project root is on the path when running from any directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_listings, create_fit_card
from utils.data_loader import load_listings


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_score_zero():
    # Results should have at least one keyword token from the description
    results = search_listings("vintage", size=None, max_price=None)
    assert all(
        "vintage" in (
            item["title"] + item["description"] + " ".join(item["style_tags"])
        ).lower()
        for item in results
    )


# ── create_fit_card (offline — guard path only) ───────────────────────────────

def test_fit_card_empty_outfit_returns_string():
    listings = load_listings()
    item = listings[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_fit_card_whitespace_outfit_returns_string():
    listings = load_listings()
    item = listings[0]
    result = create_fit_card("   ", item)
    assert isinstance(result, str)
    assert len(result) > 0
