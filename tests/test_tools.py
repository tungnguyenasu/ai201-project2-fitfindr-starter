"""
Tool-level tests for FitFindr.

Run from the project root with:  pytest tests/

Each tool has at least one test per failure mode. The two LLM-backed tools
(suggest_outfit, create_fit_card) have their non-LLM failure modes tested
without a network call; the live-generation tests are skipped automatically
when GROQ_API_KEY is not set so the suite always runs green offline.
"""

import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
needs_llm = pytest.mark.skipif(not HAS_KEY, reason="GROQ_API_KEY not set")


# ── Tool 1: search_listings ─────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # No matching item → empty list, not an exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Size matching is a case-insensitive substring match.
    results = search_listings("jeans", size="30", max_price=None)
    assert all("30" in item["size"] for item in results)


def test_search_sorted_by_relevance():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) > 1
    # Best match first: a top result should carry a relevant style tag.
    top_tags = " ".join(results[0]["style_tags"]).lower()
    assert "vintage" in top_tags or "graphic" in top_tags or "tee" in top_tags


# ── Tool 2: suggest_outfit ──────────────────────────────────────────────────

def _sample_item():
    return search_listings("vintage graphic tee", size=None, max_price=50)[0]


def test_suggest_outfit_empty_wardrobe_no_crash():
    # Failure mode: empty wardrobe must not crash; always a non-empty string.
    out = suggest_outfit(_sample_item(), get_empty_wardrobe())
    assert isinstance(out, str)
    assert out.strip() != ""


@needs_llm
def test_suggest_outfit_example_wardrobe():
    out = suggest_outfit(_sample_item(), get_example_wardrobe())
    assert isinstance(out, str)
    assert len(out.strip()) > 20


# ── Tool 3: create_fit_card ─────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    # Failure mode: empty/whitespace outfit → descriptive error string.
    msg = create_fit_card("", _sample_item())
    assert isinstance(msg, str)
    assert "outfit" in msg.lower()

    msg_ws = create_fit_card("   ", _sample_item())
    assert isinstance(msg_ws, str)
    assert msg_ws.strip() != ""


@needs_llm
def test_create_fit_card_outputs_vary():
    item = _sample_item()
    outfit = "Pair it with baggy jeans and chunky sneakers."
    a = create_fit_card(outfit, item)
    b = create_fit_card(outfit, item)
    assert isinstance(a, str) and a.strip() != ""
    # High temperature should make repeated captions differ.
    assert a != b
