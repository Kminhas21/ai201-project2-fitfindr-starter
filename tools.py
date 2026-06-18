"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

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

_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(messages: list[dict], temperature: float) -> str:
    """Call the LLM and return the response text."""
    return _get_groq_client().chat.completions.create(
        model=_MODEL,
        messages=messages,
        temperature=temperature,
    ).choices[0].message.content.strip()


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
        description: Keywords describing what the user is looking for.
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive substring (e.g., "m" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts sorted by relevance (best first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()
    
    # Filter by price
    if max_price is not None:
        listings = [item for item in listings if item["price"] <= max_price]

    # Filter by size (lenient substring match)
    if size:
        size_lower = size.lower()
        listings = [item for item in listings if size_lower in item["size"].lower()]

    # Score by keyword overlap with description
    tokens = description.lower().split()
    scored = []
    for item in listings:
        searchable = " ".join([
            item["title"],
            item["description"],
            " ".join(item["style_tags"]),
            item["category"],
            " ".join(item["colors"]),
            item.get("brand") or "",
        ]).lower()
        score = sum(1 for token in tokens if token in searchable)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key. May be empty.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice instead.
    """
    items = wardrobe.get("items") or []

    if not items:
        prompt = (
            f"A shopper found this secondhand item: {new_item['title']} "
            f"({new_item['category']}, {new_item['condition']} condition, "
            f"style: {', '.join(new_item['style_tags'])}). "
            "They have no wardrobe entered yet. Suggest what kinds of pieces "
            "would pair well with this item and what overall vibe it suits. "
            "2–3 sentences, practical and specific."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {w['name']} ({', '.join(w['style_tags'])})" for w in items
        )
        prompt = (
            f"A shopper found this secondhand item: {new_item['title']} "
            f"({new_item['category']}, style: {', '.join(new_item['style_tags'])}, "
            f"colors: {', '.join(new_item['colors'])}).\n\n"
            f"Their wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1–2 complete outfits using this new item and named pieces "
            "from the wardrobe. Be specific — name the wardrobe pieces. "
            "Keep it to 3–4 sentences total."
        )

    try:
        return _chat([{"role": "user", "content": prompt}], temperature=0.7)
    except Exception:
        return (
            f"Style tip: {new_item['title']} works well with neutral basics. "
            "Try pairing it with jeans or trousers in a complementary color."
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
        If outfit is empty, returns a descriptive error string — does NOT raise.
    """
    if not outfit or not outfit.strip():
        return "Can't make a fit card — no outfit suggestion available yet."

    prompt = (
        f"Write a casual, authentic OOTD caption (2–4 sentences) for this outfit:\n\n"
        f"New find: {new_item['title']} — ${new_item['price']} on {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Rules: mention the item name, price, and platform once each, naturally. "
        "Sound like a real person posting, not a product description. "
        "Capture the vibe in specific terms. Use lowercase. Can include 1–2 relevant emojis."
    )

    try:
        return _chat([{"role": "user", "content": prompt}], temperature=1.0)
    except Exception:
        return (
            f"just thrifted the {new_item['title']} off {new_item['platform']} "
            f"for ${new_item['price']} and i'm obsessed 🖤"
        )
