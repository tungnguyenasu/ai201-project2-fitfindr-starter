# FitFindr 🛍️

FitFindr is a small tool-using agent that helps someone shop secondhand clothing.
You describe what you want in plain language ("vintage graphic tee under $30, size M"),
and the agent finds a matching listing, styles it against your wardrobe, and writes a
short shareable "fit card" caption for it.

The point of the project is the **planning loop**: the agent does not blindly run all
of its tools every time. It makes a decision after each step and changes its behavior
based on what the previous tool returned.

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file in the project root (free key at
[console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Two of the three tools call Groq's `llama-3.3-70b-versatile`. The third
(`search_listings`) and all of the error-handling paths run fully offline.

## Running it

```bash
python app.py        # launches the Gradio UI (watch the terminal for the URL, usually http://localhost:7860)
python agent.py      # runs two CLI test interactions (a happy path + a no-results path)
pytest tests/        # runs the tool test suite
```

---

## Project layout

```
ai201-project2-fitfindr-starter/
├── tools.py          # the three tools (search_listings, suggest_outfit, create_fit_card)
├── agent.py          # run_agent(): query parsing + the planning loop + session state
├── app.py            # Gradio UI + handle_query(): maps the session dict to 3 panels
├── tests/
│   └── test_tools.py # one test per failure mode; LLM tests skip when no API key
├── data/
│   ├── listings.json         # 40 mock secondhand listings
│   └── wardrobe_schema.json  # wardrobe format + example wardrobe + empty template
├── utils/
│   └── data_loader.py        # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
└── planning.md       # the spec this implementation was built from
```

---

## Tool inventory

### 1. `search_listings(description, size, max_price) -> list[dict]`

**Purpose:** Find listings in the mock dataset that match the user's request, ranked
best-match-first. This runs first because the agent has nothing to style until it has a
real item.

| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Search keywords, e.g. `"vintage graphic tee"` |
| `size` | `str \| None` | Size filter; `None` skips size filtering. Matched case-insensitively as a substring (`"30"` matches `"W30 L30"`) |
| `max_price` | `float \| None` | Inclusive price ceiling; `None` skips price filtering |

**Returns:** A `list[dict]` of listing dicts (fields: `id`, `title`, `description`,
`category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`),
sorted by relevance score, highest first. Returns `[]` when nothing matches — never raises.

**How it ranks:** keywords from `description` are scored against each listing. A match in
the title, style tags, category, colors, or brand is worth 2 points; a match only in the
long free-text description is worth 1. Listings scoring 0 are dropped. (Common filler
words like "looking", "for", "the" are stripped before scoring.)

### 2. `suggest_outfit(new_item, wardrobe) -> str`

**Purpose:** Turn a selected listing into one or two concrete outfit ideas, using the
user's actual wardrobe pieces when it has them.

| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | A listing dict (the item being considered) |
| `wardrobe` | `dict` | Has an `"items"` key (a list of wardrobe-item dicts). May be empty |

**Returns:** A non-empty `str`. With a populated wardrobe it names specific pieces ("pair
it with your Baggy Straight-Leg Jeans and Chunky White Sneakers"). With an **empty**
wardrobe it gives general styling advice instead of failing.

### 3. `create_fit_card(outfit, new_item) -> str`

**Purpose:** Write a casual, social-media-ready caption (2–4 sentences) for the look.

| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The outfit suggestion from `suggest_outfit` |
| `new_item` | `dict` | The selected listing dict |

**Returns:** A `str` caption that mentions the item, its price, and the platform once
each. If `outfit` is empty/whitespace, it returns a descriptive error string instead of a
caption. Uses a high LLM temperature (0.95) so repeated calls vary.

---

## How the planning loop works (the decisions the agent makes)

`run_agent(query, wardrobe)` in [agent.py](agent.py) is the loop. It is **conditional** —
each step depends on the previous result, and two steps can short-circuit the whole run.

1. **Initialize state.** `_new_session()` builds one `session` dict that holds everything
   for this interaction.
2. **Parse the query** with regex (not the LLM — the queries are simple and predictable).
   It pulls a `max_price` out of phrases like "under $30", a `size` out of "size M" /
   "in size 8", and treats whatever text is left over as the search `description`.
   Example: `"vintage graphic tee under $30, size M"` →
   `{description: "vintage graphic tee", size: "M", max_price: 30.0}`.
3. **Search.** Calls `search_listings()` with the parsed values.
4. **Decision point #1 — did we find anything?**
   - If `search_results == []`: set `session["error"]`, **return immediately**, and do
     *not* call `suggest_outfit` or `create_fit_card`. There is no item to style, so
     running the styling tools on empty input would be meaningless.
   - Otherwise: select the top-ranked listing as `session["selected_item"]` and continue.
5. **Suggest an outfit** for the selected item against the wardrobe.
6. **Decision point #2 — did we get usable outfit text?** `suggest_outfit` is designed to
   always return something, but if it ever comes back empty the agent sets an error and
   returns before building a fit card from nothing.
7. **Create the fit card** from the outfit + selected item, then return the session.

So the agent's behavior genuinely diverges: a matching query flows through all three
tools; a no-match query stops after step 4 with only an error set.

---

## State management

There is one mutable `session` dict per interaction. It is the single source of truth, and
each tool's result is written back into it before the next tool reads from it:

```python
session = {
    "query":             query,        # original text
    "parsed":            {},           # {description, size, max_price}
    "search_results":    [],           # everything search_listings returned
    "selected_item":     None,         # results[0] — the item we style
    "wardrobe":          wardrobe,
    "outfit_suggestion": None,         # what suggest_outfit returned
    "fit_card":          None,         # what create_fit_card returned
    "error":             None,         # set only if the run stopped early
}
```

The item flows by reference: `session["selected_item"]` is passed into `suggest_outfit`,
and the **same object** is later passed into `create_fit_card` — there is no re-prompting
the user and no hardcoded values between steps. (Verified by instrumenting the tools: the
`id()` of `selected_item` is identical at every step, and the stored `outfit_suggestion`
is byte-for-byte what `create_fit_card` received.)

`app.py`'s `handle_query()` is the only thing that reads the finished session: if
`session["error"]` is set it puts that message in the first panel and leaves the other two
blank; otherwise it formats `selected_item` into readable text and returns it alongside
`outfit_suggestion` and `fit_card`.

---

## Error handling (per tool)

| Tool | Failure mode | What the agent does |
|---|---|---|
| `search_listings` | No listing matches | Returns `[]` (no exception). The agent sets `session["error"]`, returns early, and skips the styling tools. |
| `search_listings` | Empty / whitespace query | `handle_query()` guards this before `run_agent()` is ever called and returns "Please enter what you're looking for." |
| `suggest_outfit` | Wardrobe is empty | Not treated as a failure — it calls the LLM with a "general advice" prompt and still returns useful text. |
| `suggest_outfit` | LLM call fails / returns empty | Caught; returns a fallback styling string so the run can continue. |
| `create_fit_card` | `outfit` missing/whitespace | Returns a descriptive error string ("I can't create a fit card because the outfit suggestion is missing…") instead of raising. |
| `create_fit_card` | LLM call fails | Caught; returns a simple fallback caption built from the item title, price, and platform. |

**Concrete example from testing (the no-results branch).** Running the query
`"designer ballgown size XXS under $5"` against the example wardrobe, with the styling
tools temporarily replaced by tripwires:

```
search_results   : []
selected_item    : None
outfit_suggestion: None
fit_card         : None
error set         : True
tools called on no-results path: NONE (correct)
```

This confirms the agent short-circuits: `fit_card` stays `None` and `suggest_outfit` is
never invoked when the search comes back empty.

**Concrete example (empty-outfit guard).** `create_fit_card("", item)` returns
`"I can't create a fit card because the outfit suggestion is missing. Please generate an
outfit first."` rather than throwing — verified in `tests/test_tools.py`.

---

## Spec reflection

The build followed `planning.md` closely, and a few things were worth noting:

- **The conditional loop was the right call.** The biggest spec decision — stop early on
  empty search results instead of running all tools every time — is exactly what made the
  agent's behavior differ between inputs. Wiring all three tools unconditionally would
  have produced an outfit suggestion for a search that found nothing.
- **Regex parsing held up** for the planned query shapes ("under $X", "size M/8/XXS").
  It is intentionally simple; queries that phrase price or size unusually (e.g. "no more
  than thirty dollars") fall back to being part of the description, which is an acceptable
  degradation rather than a crash.
- **The relevance score needed tuning beyond the bare spec.** Plain keyword overlap
  matched too many listings equally; weighting title/tag matches above description matches
  pushed the genuinely-vintage tees above incidental "tee" mentions.
- **Known data issue:** several titles in `data/listings.json` contain double-encoded
  em-dashes (`â€"`), so they render with a stray character. This is a defect in the
  provided data file, not in the agent logic, and does not affect search or state flow.

---

## AI usage

I used Claude Code as the AI tool while implementing, one piece at a time, and reviewed
each result against `planning.md` before keeping it.

**Instance 1 — `search_listings`.**
*Input I gave it:* the "Tool 1: search_listings" section of `planning.md` (inputs, return
shape, the "returns `[]`, never raises" failure mode), the existing function signature
from `tools.py`, and the instruction to use `load_listings()` rather than re-reading JSON.
*What it produced:* a working filter-then-score implementation that loaded listings,
applied the price and size filters, and ranked by keyword overlap.
*What I changed:* the first version scored every field equally, which ranked an incidental
"baby tee" alongside an actual "vintage band tee" for the query "vintage graphic tee." I
overrode it to weight matches in the title/style-tags/category 2× over matches in the long
description, and added a stopword list so filler words like "looking"/"for" didn't inflate
scores. I verified the three planned test calls before moving on.

**Instance 2 — the planning loop (`run_agent`).**
*Input I gave it:* the "Planning Loop," "State Management," and "Architecture" (the ASCII
agent diagram) sections of `planning.md`, plus the `run_agent()` signature and numbered
TODOs from `agent.py`.
*What it produced:* the session-based loop with the early-return-on-empty-results branch.
*What I checked and changed:* I specifically reviewed that it branched on the
`search_listings` result and did **not** call all three tools unconditionally — that was
the milestone's key requirement. I kept the early return, and added a second guard (decision
point #2) so a hypothetical empty outfit string can't flow into `create_fit_card`. I then
verified state identity by instrumenting the tools to confirm the same `selected_item`
object reached both styling tools with no re-entry or hardcoded values in between.
