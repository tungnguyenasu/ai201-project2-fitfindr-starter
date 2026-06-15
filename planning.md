# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**

`search_listings` searches the mock secondhand listings dataset for items that match the user’s requested clothing description, optional size, and optional maximum price. It filters out listings that do not meet the price or size constraints, then scores the remaining listings by keyword overlap with the requested description. The best matching listings are returned first.

**Input parameters:**

- `description` (str): The clothing description or search keywords from the user, such as `"vintage graphic tee"`, `"black combat boots"`, or `"90s track jacket"`.
- `size` (str | None): The requested size filter. If the user gives a size like `"M"`, `"L"`, or `"8"`, the tool filters for listings whose size contains that value. If the user does not provide a size, this is `None` and size filtering is skipped.
- `max_price` (float | None): The user’s maximum price. If the user says `"under $30"`, this should be `30.0`. If the user does not provide a price limit, this is `None` and price filtering is skipped.

**What it returns:**

A `list[dict]` of matching listing dictionaries, sorted by relevance from best match to weakest match.

Each returned listing dictionary contains:

- `id` (str)
- `title` (str)
- `description` (str)
- `category` (str)
- `style_tags` (list[str])
- `size` (str)
- `condition` (str)
- `price` (float)
- `colors` (list[str])
- `brand` (str | None)
- `platform` (str)

Example return value:

```python
[
    {
        "id": "l_001",
        "title": "Vintage Band Tee — Faded Grey",
        "description": "Soft faded graphic tee with a worn-in vintage band look.",
        "category": "tops",
        "style_tags": ["vintage", "grunge", "band tee", "graphic tee", "streetwear"],
        "size": "L",
        "condition": "fair",
        "price": 19.0,
        "colors": ["grey", "black"],
        "brand": None,
        "platform": "depop"
    }
]

What happens if it fails or returns nothing:

If no listings match the description, size, and max price, the tool returns an empty list [] instead of raising an exception. The agent checks for this empty result immediately. If the list is empty, the agent sets session["error"] to a helpful message and returns early. It does not call suggest_outfit or create_fit_card because there is no selected item to style.

Example agent response:

I couldn’t find any listings that match “designer ballgown” in size XXS under $5. Try using a broader description, increasing your max price, or removing the size filter.

---

### Tool 2: suggest_outfit

What it does:

suggest_outfit creates one or two outfit ideas using the selected thrift listing and the user’s wardrobe. If the wardrobe has items, the tool should use specific named wardrobe pieces when possible. If the wardrobe is empty, it should still return useful general styling advice for the new item instead of failing.

Input parameters:

- new_item (dict): A single listing dictionary selected from the results of search_listings. This is usually the first result in session["search_results"].
- wardrobe (dict): A wardrobe dictionary with an "items" key. The value is a list of wardrobe item dictionaries. Each wardrobe item can include:
     id (str)
     name (str)
     category (str)
     colors (list[str])
     style_tags (list[str])
     notes (str | None)

What it returns:

A non-empty str containing one or two complete outfit suggestions.

For an example wardrobe, the output should mention actual pieces from the wardrobe, such as:

     Pair the faded grey vintage band tee with your baggy straight-leg jeans and chunky white sneakers for an easy streetwear look. Add the vintage black denim jacket if you want a more grunge feel, and finish with the black crossbody bag.

For an empty wardrobe, the output should give general advice, such as:

     Since your wardrobe is empty right now, I’d style this graphic tee with relaxed denim, chunky sneakers, and a black jacket for a casual grunge-inspired look.

What happens if it fails or returns nothing:

If wardrobe["items"] is empty, the tool should not crash. It should call the LLM with a prompt asking for general styling advice using the new item’s title, category, style tags, colors, and platform. The returned string should explain what kinds of pieces would pair well with the item.

If the LLM call fails or returns an empty response, the tool should return a fallback string like:

     I found the item, but I couldn’t generate a detailed outfit suggestion. As a backup, style it with simple basics, a complementary shoe, and one accessory that matches the item’s color or vibe.

---

### Tool 3: create_fit_card

What it does:

create_fit_card turns the outfit suggestion and selected thrift item into a short, shareable outfit caption. The tone should sound casual and social-media-ready, not like a product description. It should mention the item, price, and platform naturally.

Input parameters:

- outfit (str): The outfit suggestion returned by suggest_outfit.
- new_item (dict): The selected thrift listing stored in session["selected_item"].

What it returns:

A str containing a 2–4 sentence fit card caption.

The caption should:

- Mention the thrifted item naturally.
- Include the item price.
- Include the platform once.
- Capture the outfit vibe.
- Sound casual and different for different inputs.

Example return value:

     thrifted this faded band tee on depop for $19 and it instantly became a baggy-jeans uniform. chunky sneakers, black denim, zero effort, full thrift energy.

What happens if it fails or returns nothing:

If outfit is empty, missing, or only whitespace, the tool returns a descriptive error message string instead of raising an exception.

Example return value:

     I can’t create a fit card because the outfit suggestion is missing. Please generate an outfit first.

If the LLM fails, the tool should return a simple fallback caption based on the item title, price, platform, and outfit string.

---

### Additional Tools (if any)

No additional tools for the required version.

Possible stretch feature later:

Optional Stretch Tool: compare_price

What it does:

Compares the selected item’s price to similar listings in the mock dataset and labels the price as low, fair, or high.

Input parameters:

- item (dict): The selected listing.
- all_listings (list[dict]): The full listings dataset.

What it returns:

A str explaining whether the item is fairly priced compared with similar listings.

What happens if it fails or returns nothing:

If no comparable listings are found, it returns:

     I couldn’t find enough similar listings to compare the price confidently.

This stretch tool will not be implemented until after the required features are complete.

---

## Planning Loop

How does your agent decide which tool to call next?

The agent uses a conditional planning loop inside run_agent(query, wardrobe). It does not call all tools blindly. Each step depends on the result of the previous step.

Step 1: Start a new session

     The agent calls _new_session(query, wardrobe) to create a session dictionary.

     Initial session fields:

     session = {
     "query": query,
     "parsed": {},
     "search_results": [],
     "selected_item": None,
     "wardrobe": wardrobe,
     "outfit_suggestion": None,
     "fit_card": None,
     "error": None,
     }
Step 2: Parse the user query

     The agent extracts three values from the natural language query:

          - description
          - size
          - max_price

     I will use regex and string cleanup instead of an LLM for parsing because the expected queries are simple and mostly include phrases like "under $30" or "size M".

     Parsing rules:

     1. Find price using patterns like:

          - "under $30"
          - "under 30"
          - "below $30"
          - "less than $30"

     Store this as:

     max_price = 30.0

     2. Find size using patterns like:

          - "size M"
          - "in size M"
          - "size 8"

     Store this as:

     size = "M"
     3. Build description by removing the price phrase and size phrase from the query. The remaining search phrase becomes the description.

     Example:

     query = "vintage graphic tee under $30, size M"

     session["parsed"] = {
     "description": "vintage graphic tee",
     "size": "M",
     "max_price": 30.0,
     }

     If no price is found:

     max_price = None

     If no size is found:

     size = None

Step 3: Call search_listings

     The agent calls:

     results = search_listings(
     description=session["parsed"]["description"],
     size=session["parsed"]["size"],
     max_price=session["parsed"]["max_price"],
     )

     Then it stores the results:

     session["search_results"] = results

Step 4: Branch based on search results

     If results == [], the agent stops early.

     session["error"] = (
     "I couldn't find any listings that match your request. "
     "Try a broader description, a higher max price, or removing the size filter."
     )
     return session

     The agent does not call suggest_outfit or create_fit_card in this branch.

     If results are found, the agent selects the top result:

     session["selected_item"] = results[0]

Step 5: Call suggest_outfit

     The agent calls:

     outfit = suggest_outfit(
     new_item=session["selected_item"],
     wardrobe=session["wardrobe"],
     )

     Then it stores:

     session["outfit_suggestion"] = outfit

     If the wardrobe is empty, suggest_outfit still returns general styling advice. This is not an early-stop error.

     If outfit is missing or empty after the tool call, the agent sets an error and returns early:

     session["error"] = (
     "I found a listing, but I couldn't generate an outfit suggestion. "
     "Try again with a different item or wardrobe."
     )
     return session
Step 6: Call create_fit_card

     The agent calls:

     fit_card = create_fit_card(
     outfit=session["outfit_suggestion"],
     new_item=session["selected_item"],
     )

     Then it stores:

     session["fit_card"] = fit_card
Step 7: Return completed session

     If no early error occurred, the final session contains:

          - original query
          - parsed parameters
          - search results
          - selected item
          - wardrobe
          - outfit suggestion
          - fit card
          - error = None

     The UI can then display the selected listing, outfit suggestion, and fit card in the three Gradio panels.

---

## State Management

How does information from one tool get passed to the next?

The agent uses a single session dictionary as the state object for one interaction. This session is created at the start of run_agent() and returned at the end. Each tool result is stored in the session before the next tool is called.

State fields
     - session["query"]: The original user query.
     - session["parsed"]: The parsed search parameters:
     - description
     - size
     - max_price
     - session["search_results"]: The full list returned by search_listings.
     - session["selected_item"]: The top listing selected from search_results.
     - session["wardrobe"]: The wardrobe passed into run_agent.
     - session["outfit_suggestion"]: The string returned by suggest_outfit.
     - session["fit_card"]: The string returned by create_fit_card.
     - session["error"]: A helpful error message if the agent stops early.

State flow
     - User query is stored in session["query"].
     - Parsed values are stored in session["parsed"].
     - search_listings uses session["parsed"].
     - Search results are stored in session["search_results"].
     - The first result is stored in session["selected_item"].
     - suggest_outfit receives session["selected_item"] and session["wardrobe"].
     - The outfit response is stored in session["outfit_suggestion"].
     - create_fit_card receives session["outfit_suggestion"] and session["selected_item"].
     - The final caption is stored in session["fit_card"].

This lets the selected item flow from the search tool into the outfit tool and then into the fit card tool without asking the user to re-enter information.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|

| `search_listings` | No results match the query| The tool returns `[]`. The agent sets `session["error"]` to a message explaining that no listings matched. It suggests trying a broader description, higher price, or removing the size filter. The agent returns early and does not call the other tools. |
| `search_listings` | Query is too vague or empty after parsing | The agent uses the cleaned query as the description if possible. If the user query is empty, `handle_query()` returns an error before calling `run_agent()`.                                                                              
| `suggest_outfit`  | Wardrobe is empty | The tool still returns a useful styling suggestion using general clothing categories instead of named wardrobe items. This is not treated as a full agent failure.                                                           
| `suggest_outfit`  | LLM call fails or returns empty text | The tool returns a fallback styling string using the item’s category, style tags, and colors. The agent stores that fallback in `session["outfit_suggestion"]`.                                                                                
| `create_fit_card` | Outfit input is missing or incomplete | The tool returns a descriptive error string instead of raising an exception. The agent stores the message in `session["fit_card"]` or sets `session["error"]` if needed.                                                                           
| `create_fit_card` | LLM call fails | The tool returns a simple fallback caption using the selected item’s title, price, platform, and outfit vibe.                                                                             

---

## Architecture

     User query
     │
     ▼
     Gradio UI / app.py
     │
     │ user_query + wardrobe_choice
     ▼
     handle_query(user_query, wardrobe_choice)
     │
     │ chooses get_example_wardrobe()
     │ or get_empty_wardrobe()
     ▼
     run_agent(query, wardrobe)
     │
     ▼
     _new_session(query, wardrobe)
     │
     ▼
     Session state initialized
     │
     ├── query
     ├── parsed = {}
     ├── search_results = []
     ├── selected_item = None
     ├── wardrobe
     ├── outfit_suggestion = None
     ├── fit_card = None
     └── error = None
     │
     ▼
     Parse query
     │
     ├── description
     ├── size
     └── max_price
     │
     ▼
     session["parsed"] = parsed values
     │
     ▼
     search_listings(description, size, max_price)
     │
     ├── results == []
     │       │
     │       ▼
     │   session["error"] =
     │   "No listings found. Try a broader search,
     │    higher price, or no size filter."
     │       │
     │       ▼
     │   Return session early
     │
     └── results == [item, ...]
               │
               ▼
          session["search_results"] = results
               │
               ▼
          session["selected_item"] = results[0]
               │
               ▼
          suggest_outfit(selected_item, wardrobe)
               │
               ├── wardrobe has items
               │       ▼
               │   Suggest outfit using named wardrobe pieces
               │
               └── wardrobe empty
                         ▼
                    Suggest general styling advice
               │
               ▼
          session["outfit_suggestion"] = outfit
               │
               ▼
          create_fit_card(outfit_suggestion, selected_item)
               │
               ├── outfit missing
               │       ▼
               │   Return descriptive error string
               │
               └── outfit exists
                         ▼
                    Generate social caption
               │
               ▼
          session["fit_card"] = caption
               │
               ▼
          Return completed session
               │
               ▼
     handle_query formats outputs
               │
               ▼
     User sees:
     - Top listing found
     - Outfit idea
     - Fit card
---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
I will use ChatGPT or Claude to help implement one tool at a time in tools.py. I will not ask the AI to implement the whole project at once.

Tool 1: search_listings

     What I will give the AI tool:

          The Tool 1: search_listings section from this planning.md.
          The existing function signature from tools.py.
          The instruction to use load_listings() from utils/data_loader.py.

     What I expect it to produce:

     A Python implementation that:

          Calls load_listings().
          Filters by max_price if provided.
          Filters by size if provided.
          Scores listings using keyword overlap across title, description, category, style tags, colors, and brand.
          Returns matching listing dictionaries sorted by score.
          Returns [] if there are no matches.

     How I will verify it before using it:

     I will check that the generated code does not re-read JSON manually and does not crash on no results. I will test:

          search_listings("vintage graphic tee", size=None, max_price=50)
          search_listings("designer ballgown", size="XXS", max_price=5)
          search_listings("jacket", size=None, max_price=10)
     
Tool 2: suggest_outfit

     What I will give the AI tool:

          The Tool 2: suggest_outfit section from this planning.md.
          The existing function signature from tools.py.
          The wardrobe schema details from this plan.

     What I expect it to produce:

     A Python implementation that:

          Accepts new_item and wardrobe.
          Checks whether wardrobe["items"] is empty.
          Builds one prompt for a normal wardrobe.
          Builds a different prompt for an empty wardrobe.
          Calls Groq with llama-3.3-70b-versatile.
          Returns a non-empty string.
          Uses a fallback response if the LLM call fails.

     How I will verify it before using it:

     I will call it with both:

          get_example_wardrobe()
          get_empty_wardrobe()

     I will confirm both calls return useful strings instead of exceptions.

Tool 3: create_fit_card

     What I will give the AI tool:

          The Tool 3: create_fit_card section from this planning.md.
          The existing function signature from tools.py.
          The requirement that the caption should be 2–4 sentences and social-media-ready.

     What I expect it to produce:

     A Python implementation that:

          Checks whether outfit is empty.
          Returns an error message string if outfit is missing.
          Builds a prompt using the item title, price, platform, colors, style tags, and outfit.
          Calls Groq with a higher temperature so outputs vary.
          Returns the caption as a string.
          Uses a fallback caption if the LLM call fails.

     How I will verify it before using it:

     I will test:

          create_fit_card("", selected_item)
          create_fit_card("Pair it with baggy jeans and chunky sneakers.", selected_item)

     I will run the second call multiple times and check that the outputs are not identical every time.

**Milestone 4 — Planning loop and state management:**
     I will use ChatGPT or Claude to help implement handle_query() in app.py.

     What I will give the AI tool:

          The State Management section from this planning.md.
          The existing app.py TODO comments.
          The expected return format: (listing_text, outfit_suggestion, fit_card).

     What I expect it to produce:

     A handle_query() implementation that:

          Checks for an empty user query.
          Selects get_example_wardrobe() or get_empty_wardrobe() based on the radio button.
          Calls run_agent().
          If session["error"] exists, returns the error in the first output panel and empty strings in the other panels.
          If successful, formats the selected item into readable listing text.
          Returns listing text, outfit suggestion, and fit card.

     How I will verify it before using it:

     I will run:

          python app.py

     Then I will test:   

          "vintage graphic tee under $30"
          "black combat boots size 8"
          "designer ballgown size XXS under $5"
---

## A Complete Interaction (Step by Step)

FitFindr helps a user search secondhand clothing listings, choose a matching item, style it with their existing wardrobe, and generate a short shareable outfit caption. The search tool runs first because the agent needs a real listing before it can suggest an outfit. If search returns no matches, the agent stops early and tells the user what to adjust instead of calling the outfit or fit card tools with empty data.

The listings dataset contains secondhand items with fields like `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. The wardrobe data has an `items` list, where each wardrobe item includes fields like `id`, `name`, `category`, `colors`, `style_tags`, and optional notes.

**Example user query:**  
"I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**  
The agent calls:

`search_listings(description="vintage graphic tee", size=None, max_price=30.0)`

The tool searches the mock listings dataset for items related to “vintage graphic tee” that cost $30 or less. One possible result is:

`Vintage Band Tee — Faded Grey`  
- category: tops  
- style_tags: vintage, grunge, band tee, graphic tee, streetwear  
- size: L  
- condition: fair  
- price: $19.00  
- platform: depop

The agent stores this item in session state as:

`session["selected_item"] = <Vintage Band Tee listing>`

**Step 2:**  
The agent calls:

`suggest_outfit(new_item=session["selected_item"], wardrobe=example_wardrobe)`

The tool uses the selected tee and the user’s wardrobe. Since the example wardrobe includes baggy straight-leg jeans, chunky white sneakers, black combat boots, a black denim jacket, and accessories, the outfit suggestion can combine the new tee with existing pieces.

Example outfit suggestion:

"Pair the faded grey vintage band tee with your baggy straight-leg jeans and chunky white sneakers for an easy streetwear look. Add the vintage black denim jacket if you want a more grunge feel, and finish with the black crossbody bag."

The agent stores this as:

`session["outfit_suggestion"] = <generated outfit suggestion>`

**Step 3:**  
The agent calls:

`create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`

The tool turns the outfit into a short shareable caption.

Example fit card:

"found this faded band tee on depop for $19 and it instantly became a baggy-jeans uniform. chunky sneakers, black denim, zero effort, full thrift energy."

The agent stores this as:

`session["fit_card"] = <generated fit card>`

**Final output to user:**  
The user sees the selected listing, the outfit suggestion, and the final fit card caption.

**Error path:**  
If `search_listings()` returns an empty list, the agent sets an error message like:

"Sorry, I couldn't find any listings that match that description, size, and price. Try raising the max price, removing the size filter, or using a broader description like 'graphic tee' instead of 'vintage band tee.'"

Then the agent stops. It does not call `suggest_outfit()` or `create_fit_card()` because there is no selected item to style.
