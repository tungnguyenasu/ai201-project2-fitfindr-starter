"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(prompt: str, temperature: float = 0.7) -> str:
    """Send a single user prompt to the LLM and return the response text.

    Raises on any client/API error so callers can apply their own fallback.
    """
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Filter by max_price (inclusive) if a ceiling was given.
    if max_price is not None:
        listings = [item for item in listings if item.get("price", 0) <= max_price]

    # 2. Filter by size (case-insensitive substring match) if a size was given.
    if size:
        size_lc = size.strip().lower()
        listings = [
            item for item in listings
            if size_lc in str(item.get("size", "")).lower()
        ]

    # 3. Score each remaining listing by keyword overlap with `description`.
    keywords = _tokenize(description)

    scored = []
    for item in listings:
        score = _score_listing(item, keywords)
        if score > 0:
            scored.append((score, item))

    # 4 & 5. Drop zero-score listings (already done) and sort best match first.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in scored]


# Common filler words that add no search signal.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "of", "in", "on", "to",
    "some", "any", "that", "this", "i", "im", "am", "looking", "want", "need",
    "size", "under", "over", "below", "above", "less", "than", "around",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into meaningful keyword tokens."""
    raw = "".join(c.lower() if c.isalnum() else " " for c in (text or ""))
    return [tok for tok in raw.split() if len(tok) >= 2 and tok not in _STOPWORDS]


def _score_listing(item: dict, keywords: list[str]) -> int:
    """Score a listing by how many query keywords overlap its searchable fields.

    Matches in the title and style tags are weighted more heavily than matches
    in the longer free-text description, since they are stronger relevance
    signals.
    """
    if not keywords:
        return 0

    strong = " ".join([
        str(item.get("title", "")),
        " ".join(item.get("style_tags", [])),
        str(item.get("category", "")),
        " ".join(item.get("colors", [])),
        str(item.get("brand") or ""),
    ]).lower()
    weak = str(item.get("description", "")).lower()

    score = 0
    for kw in keywords:
        if kw in strong:
            score += 2
        elif kw in weak:
            score += 1
    return score


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = (wardrobe or {}).get("items", [])

    item_desc = (
        f"- Title: {new_item.get('title', 'an item')}\n"
        f"- Category: {new_item.get('category', 'unknown')}\n"
        f"- Style tags: {', '.join(new_item.get('style_tags', [])) or 'n/a'}\n"
        f"- Colors: {', '.join(new_item.get('colors', [])) or 'n/a'}\n"
        f"- Platform: {new_item.get('platform', 'a secondhand app')}"
    )

    if not items:
        # Empty wardrobe → general styling advice, still a useful response.
        prompt = (
            "You are a friendly personal stylist. A shopper is considering this "
            "secondhand item but has not told you anything about their existing "
            "wardrobe:\n\n"
            f"{item_desc}\n\n"
            "Suggest one or two complete outfit ideas using GENERAL clothing "
            "categories (e.g. 'relaxed denim', 'chunky sneakers', 'a black "
            "jacket'). Explain what kinds of pieces pair well and what vibe the "
            "item suits. Keep it to 2-4 sentences, warm and practical."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {it.get('name', 'item')} "
            f"({it.get('category', '')}; "
            f"colors: {', '.join(it.get('colors', [])) or 'n/a'}; "
            f"tags: {', '.join(it.get('style_tags', [])) or 'n/a'})"
            for it in items
        )
        prompt = (
            "You are a friendly personal stylist. A shopper is considering this "
            "secondhand item:\n\n"
            f"{item_desc}\n\n"
            "Here is the shopper's existing wardrobe:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest one or two complete outfit ideas that pair the new item with "
            "SPECIFIC named pieces from the wardrobe above (refer to them by their "
            "names). Keep it to 2-4 sentences, warm and practical."
        )

    try:
        result = _chat(prompt, temperature=0.7)
        if result:
            return result
    except Exception:
        pass

    # Fallback if the LLM is unavailable or returns nothing.
    return (
        "I found the item, but I couldn't generate a detailed outfit suggestion. "
        "As a backup, style it with simple basics, a complementary shoe, and one "
        "accessory that matches the item's color or vibe."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty / whitespace-only outfit.
    if not outfit or not outfit.strip():
        return (
            "I can't create a fit card because the outfit suggestion is missing. "
            "Please generate an outfit first."
        )

    title = new_item.get("title", "this thrifted piece")
    price = new_item.get("price")
    price_str = f"${price:g}" if isinstance(price, (int, float)) else "a steal"
    platform = new_item.get("platform", "a secondhand app")
    colors = ", ".join(new_item.get("colors", [])) or "n/a"
    tags = ", ".join(new_item.get("style_tags", [])) or "n/a"

    prompt = (
        "Write a short, casual social-media caption (an OOTD / 'thrift haul' "
        "post) for the outfit below. It should:\n"
        "- Be 2-4 sentences, lowercase-friendly and authentic, NOT a product "
        "description.\n"
        f"- Mention the item ('{title}'), its price ({price_str}), and the "
        f"platform ({platform}) naturally, each once.\n"
        "- Capture the specific vibe of the outfit.\n"
        "- Avoid hashtags and emojis.\n\n"
        f"Item colors: {colors}\n"
        f"Item style: {tags}\n"
        f"Outfit: {outfit}\n\n"
        "Caption:"
    )

    # 2 & 3. Higher temperature so repeated calls vary; fall back on failure.
    try:
        result = _chat(prompt, temperature=0.95)
        if result:
            return result
    except Exception:
        pass

    return (
        f"thrifted this {title.lower()} on {platform} for {price_str} and i'm "
        f"obsessed. {outfit.strip()}"
    )
