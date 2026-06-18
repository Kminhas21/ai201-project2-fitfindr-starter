# FitFindr — planning.md

---

## Tools

### Tool 1: search_listings

**What it does:**
Filters the listings dataset by price and size, then scores and ranks survivors by keyword overlap with the description. Returns the ranked matches.

**Input parameters:**
- `description` (str): keywords describing the item (e.g., "vintage graphic tee")
- `size` (str | None): size string; matched as case-insensitive substring against `listing["size"]`; None = no filter
- `max_price` (float | None): maximum price inclusive; None = no filter

**What it returns:**
A `list[dict]` of listing dicts sorted by relevance score (descending). Each dict has: `id, title, description, category, style_tags (list[str]), size, condition, price (float), colors (list[str]), brand (str|None), platform`. Returns `[]` if nothing matches — never raises.

**What happens if it fails or returns nothing:**
`run_agent` checks `if not results` immediately after the call. Sets `session["error"]` to a message naming what was searched and suggesting the user loosen the size/price filter or rephrase. Returns the session early without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Calls the LLM to suggest 1–2 complete outfits pairing the new item with the user's wardrobe. Falls back to general styling advice if the wardrobe is empty.

**Input parameters:**
- `new_item` (dict): a listing dict returned by `search_listings`
- `wardrobe` (dict): wardrobe dict with an `"items"` key containing a list of wardrobe item dicts (may be `[]`)

**What it returns:**
A non-empty `str` with outfit suggestions. If the wardrobe is empty, returns general advice about what pairs well. Never returns `""`.

**What happens if it fails or returns nothing:**
Wrapped in `try/except`. On LLM error returns a short hardcoded styling tip string so the agent can still produce a fit card.

---

### Tool 3: create_fit_card

**What it does:**
Calls the LLM to generate a casual 2–4 sentence OOTD caption mentioning the item name, price, and platform naturally.

**Input parameters:**
- `outfit` (str): outfit suggestion from `suggest_outfit`
- `new_item` (dict): the listing dict for the thrifted item

**What it returns:**
A `str` caption. If `outfit` is empty/whitespace, returns `"Can't make a fit card — no outfit suggestion available yet."` without calling the LLM. On LLM error returns a short hardcoded fallback caption. Never raises.

**What happens if it fails or returns nothing:**
Guard runs before any LLM call for missing outfit. LLM errors caught in `try/except`; fallback caption returned.

---

## Planning Loop

`run_agent` executes these steps in order:

1. `_parse_query(query)` → `{description, size, max_price}` (LLM call, regex fallback on error). Store in `session["parsed"]`.
2. `search_listings(description, size, max_price)` → `results`. Store in `session["search_results"]`.
3. **Branch on results:**
   - `if not results`: set `session["error"]` with a specific message; `return session`. `suggest_outfit` and `create_fit_card` are **not called**.
   - `else`: continue.
4. `session["selected_item"] = results[0]`
5. `session["outfit_suggestion"] = suggest_outfit(results[0], wardrobe)`
6. `session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])`
7. `return session`

The loop is not a fixed sequence — step 3 terminates early based on what `search_listings` returned.

---

## State Management

All state lives in the `session` dict created by `_new_session(query, wardrobe)`:

| Key | Set by | Read by |
|-----|--------|---------|
| `parsed` | `_parse_query` | `search_listings` call |
| `search_results` | `search_listings` | step 3 branch check |
| `selected_item` | step 4 | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | `handle_query` (UI) |
| `error` | step 3 on empty results | `handle_query` (UI) |

No global state. Each `run_agent` call gets a fresh session.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match filters | `session["error"]` = `'No listings found for "vintage graphic tee" in size M under $30. Try removing the size filter, raising the price limit, or using different keywords.'` — loop stops, outfit/card left as None |
| `suggest_outfit` | Wardrobe is empty | LLM given a general-styling prompt (no wardrobe items) — still returns useful advice; no crash |
| `suggest_outfit` | LLM call fails | `except` returns hardcoded tip string — never returns `""` |
| `create_fit_card` | `outfit` is empty/whitespace | Returns `"Can't make a fit card — no outfit suggestion available yet."` before any LLM call |
| `create_fit_card` | LLM call fails | `except` returns hardcoded fallback caption |

---

## Architecture

```
User query
    │
    ▼
_parse_query(query)  ──[LLM fails]──► regex fallback
    │ {description, size, max_price}
    ▼
search_listings(description, size, max_price)
    │
    ├── results == []
    │       │
    │       ▼
    │   session["error"] = "No listings found..."
    │   return session  ◄──────────────────────── early exit
    │
    │ results = [item, ...]
    ▼
session["selected_item"] = results[0]
    │
    ▼
suggest_outfit(selected_item, wardrobe)
    │   empty wardrobe → general advice
    │   LLM error     → hardcoded fallback
    ▼
session["outfit_suggestion"] = "..."
    │
    ▼
create_fit_card(outfit_suggestion, selected_item)
    │   empty outfit  → error string (no LLM call)
    │   LLM error     → hardcoded fallback
    ▼
session["fit_card"] = "..."
    │
    ▼
return session  →  handle_query formats panels  →  Gradio UI
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
Used Claude. Input: Tool 1/2/3 spec blocks from this file + the `tools.py` docstrings (Args/Returns/TODO). Expected output: implementations that filter by all three params, call LLM with appropriate prompts, handle failure modes. Verified by running `pytest tests/` (offline checks) and the Milestone 5 one-liners against live Groq.

**Milestone 4 — Planning loop and state management:**
Used Claude. Input: Architecture diagram above + Planning Loop + State Management sections. Expected output: `run_agent` with the branch at step 3, session keys populated in the right order. Verified by running `python agent.py` both test cases and confirming the no-results path never calls `suggest_outfit`.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** `_parse_query` sends the query to Groq → `{"description": "vintage graphic tee", "size": null, "max_price": 30.0}`. Stored in `session["parsed"]`.

**Step 2:** `search_listings("vintage graphic tee", size=None, max_price=30.0)` — loads 40 listings, drops items over $30, scores each by token overlap with "vintage graphic tee". Returns e.g. `[{"title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "platform": "depop", ...}, ...]`. Stored in `session["search_results"]`. Results non-empty → continue.

**Step 3:** `session["selected_item"] = results[0]` (the Y2K Baby Tee).

**Step 4:** `suggest_outfit(baby_tee, example_wardrobe)` — wardrobe has 10 items. Prompt names them; LLM returns e.g. "Pair this with your baggy straight-leg jeans and chunky white sneakers for a 90s-casual look. Add the black crossbody and you're done." Stored in `session["outfit_suggestion"]`.

**Step 5:** `create_fit_card(outfit_suggestion, baby_tee)` — LLM returns e.g. "found this y2k baby tee on depop for $18 and it was made for my baggy jeans 🦋 full fit in stories". Stored in `session["fit_card"]`.

**Final output to user:** Three panels in Gradio:
- Panel 1: listing details (title, price, platform, size, condition, tags, description).
- Panel 2: the outfit suggestion from step 4.
- Panel 3: the fit card caption from step 5.
