"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Parse a natural language query into structured search params.
    Tries LLM first; falls back to regex on any error.

    Returns:
        {"description": str, "size": str | None, "max_price": float | None}
    """
    prompt = (
        "Extract search parameters from this fashion query. "
        "Return ONLY valid JSON with keys: description (str), size (str or null), max_price (number or null).\n\n"
        f"Query: {query}"
    )
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Only answer questions regarding fashion item search parameters. Always return valid JSON. If asked questiosn outside of fashion item search parameters, respond with {\"description\": \"\", \"size\": \"\", \"max_price\": \"\"}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        ).choices[0].message.content.strip()

        print("LLM response for query parsing:\n", response)
        # Strip markdown code fences if present
        if response.startswith("```"):
            response = re.sub(r"^```[a-z]*\n?", "", response)
            response = re.sub(r"\n?```$", "", response)

        parsed = json.loads(response)
        print("Parsed query parameters:\n", parsed)
        return {
            "description": str(parsed.get("description") or query),
            "size": parsed.get("size") or None,
            "max_price": float(parsed["max_price"]) if parsed.get("max_price") is not None else None,
        }
    except Exception:
        # Regex fallback
        max_price = None
        price_match = re.search(r"(?:under|below|<)\s*\$?(\d+(?:\.\d+)?)", query, re.I)
        if price_match:
            max_price = float(price_match.group(1))

        size = None
        size_match = re.search(r"\bsize\s+(\S+)|\b(xs|s|m|l|xl|xxl)\b", query, re.I)
        if size_match:
            size = (size_match.group(1) or size_match.group(2)).upper()

        return {"description": query, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the FitFindr planning loop for a single user interaction.

    Planning logic:
    1. Parse query → description/size/max_price.
    2. Call search_listings. If empty → set error, return early (no outfit/card).
    3. Select top result → suggest_outfit → create_fit_card.
    4. Return session dict.

    Args:
        query:    Natural language user request.
        wardrobe: User's wardrobe dict.

    Returns:
        Session dict. Check session["error"] first — if not None, the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    session = _new_session(query, wardrobe)

    # Step 1: parse query
    parsed = _parse_query(query)
    session["parsed"] = parsed
    results = {}
    if parsed["description"] != query:
        results = search_listings(
            description=parsed["description"],
            size=parsed.get("size"),
            max_price=parsed.get("max_price"),
        )
        session["search_results"] = results
    else:
        results = None
    

    # Branch: no results → early return
    if not results:
        parts = [f'No listings found for "{parsed["description"]}"']
        if parsed.get("size"):
            parts.append(f'in size {parsed["size"]}')
        if parsed.get("max_price") is not None:
            parts.append(f'under ${parsed["max_price"]:.0f}')
        session["error"] = (
            " ".join(parts) + ". "
            "Try removing the size filter, raising the price limit, or using different keywords."
        )
        return session

    # Step 3: select top result
    session["selected_item"] = results[0]

    # Step 4: suggest outfit
    session["outfit_suggestion"] = suggest_outfit(results[0], wardrobe)

    # Step 5: create fit card
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

def _safe_print(text: str) -> None:
    """Print text, replacing any characters the terminal can't encode."""
    print(text.encode(errors="replace").decode(errors="replace"))


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        _safe_print(f"Found: {session['selected_item']['title']}")
        _safe_print(f"\nOutfit: {session['outfit_suggestion']}")
        _safe_print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
