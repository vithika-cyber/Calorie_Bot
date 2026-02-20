# CalorieBot - Complete Architecture & System Guide

## Table of Contents

1. [What This Project Is](#what-this-project-is)
2. [How It Works (End to End)](#how-it-works-end-to-end)
3. [Project Structure](#project-structure)
4. [The Agent System (LangGraph)](#the-agent-system-langgraph)
5. [File-by-File Breakdown](#file-by-file-breakdown)
6. [Database Design](#database-design)
7. [Phase 2 Features](#phase-2-features)
8. [Multi-User Support](#multi-user-support)
9. [How Users Access the Bot](#how-users-access-the-bot)
10. [External APIs](#external-apis)
11. [Nutrition Lookup Pipeline](#nutrition-lookup-pipeline)
12. [Onboarding Flow](#onboarding-flow)
13. [Configuration & Environment](#configuration--environment)
14. [Singleton Pattern](#singleton-pattern)
15. [Logging](#logging)
16. [Key Design Decisions](#key-design-decisions)

---

## What This Project Is

CalorieBot is a Slack chatbot that lets users track what they eat using natural language. Instead of manually looking up calories and entering numbers, a user just types something like *"I had 2 eggs and toast for breakfast"* and the bot:

1. Understands what foods were mentioned (using Google Gemini AI)
2. Looks up accurate nutrition data (from the USDA government database)
3. Stores everything in a MySQL database (per user)
4. Responds with a formatted summary showing calories, macros, and daily progress

Users can also ask historical questions like *"What did I eat yesterday?"* or *"Show me last week"* and get a full food summary with per-day breakdowns.

The bot is built as an **agentic system** -- meaning it has multiple specialized "agents" that each handle one job, coordinated by an orchestrator built on **LangGraph** (a framework for building AI agent workflows).

---

## How It Works (End to End)

Here's exactly what happens when a user sends "I had 2 eggs and toast for breakfast":

```
User sends Slack DM
        |
        v
[main.py] Slack event listener receives the message
        |
        v
[orchestrator.py] process_message() is called with (user_id, team_id, message)
        |
        v
[Rate Limiter] Check if user is within 10 messages/minute limit
        |  (rejected? -> "slow down" message)
        v
[Step 1: get_user_context]
    - Looks up or creates the user in MySQL
    - Checks if they've completed onboarding
    - Gets their calorie goal (default 2000 if not set)
    - Loads last 5 conversation messages for context
        |
        v
[Step 2: route_intent]
    - First tries keyword matching (no API call needed)
    - Falls back to Gemini AI only if keywords don't match
    - Returns: { intent: "log_food", confidence: "high" }
    - If user is NOT onboarded, all messages route to onboarding
        |
        v
[Step 3: parse_food] (because intent = "log_food")
    - Sends message + conversation history to Gemini AI
    - AI returns structured JSON:
      {
        foods: [
          { name: "scrambled eggs", quantity: 2, unit: "large", meal_type: "breakfast" },
          { name: "toast", quantity: 1, unit: "slice", meal_type: "breakfast" }
        ],
        confidence: "high"
      }
        |
        v
[Step 4: lookup_nutrition]
    For each food item:
      1. Check persistent MySQL cache first
      2. If not cached, search USDA FoodData Central API
      3. Cache the result in MySQL for future lookups
      4. Scale nutrition to the user's serving size
    If USDA has no match:
      1. Ask Gemini AI to estimate the nutrition
      2. If AI also can't identify it, mark as "unknown" (0 cal)
        |
        v
[Step 5: store_food_log]
    - Saves the food log to MySQL (food_logs table)
    - Calculates daily totals so far
    - Builds a formatted Slack response with emojis and progress bar
        |
        v
[Save conversation history] User message + bot response stored for context
        |
        v
[main.py] Sends the formatted response back to the user in Slack
```

---

## Project Structure

```
count_calories/
  .env                      # Your actual API keys (git-ignored)
  .env.example              # Template showing what keys are needed
  requirements.txt          # Python dependencies
  README.md                 # Quick start guide
  ARCHITECTURE.md           # This file
  calorie_bot.log           # Runtime log file (auto-created)
  docs/
    agent_flowchart.png     # Visual diagram of the agent flow
    nutrition_pipeline.png  # Visual diagram of the nutrition lookup
  
  src/
    __init__.py             # Package marker, contains version
    main.py                 # Entry point: Slack event handlers, bot startup
    config.py               # Loads .env into a Settings object (pydantic)
    
    agents/                 # The "brain" - AI agents that process messages
      __init__.py
      orchestrator.py       # LangGraph workflow that coordinates everything
      router_agent.py       # Classifies user intent (keyword match + Gemini fallback)
      food_parser.py        # Extracts structured food data from natural language
      nutrition_lookup.py   # Looks up calories/macros from USDA + AI fallback
      storage_agent.py      # All database read/write operations + conversation history
    
    services/               # Wrappers for external APIs
      __init__.py
      ai_service.py         # Google Gemini API wrapper (food parsing, intent detection)
      usda_service.py       # USDA FoodData Central API wrapper (with persistent cache)
    
    database/               # Database layer
      __init__.py
      database.py           # SQLAlchemy engine, session management
      models.py             # ORM models: User, FoodLog, Goal, ConversationMessage, NutritionCache
    
    utils/                  # Pure helper functions (no API calls, no DB)
      __init__.py
      calculations.py       # BMR, TDEE, calorie goal math
      formatters.py         # Builds Slack-formatted response messages
      rate_limiter.py       # Per-user token bucket rate limiter
  
  tests/                    # Test directory (placeholder)
    __init__.py
```

---

## The Agent System (LangGraph)

LangGraph is a framework that lets you define AI workflows as a **directed graph**. Each node in the graph is a function (an "agent step"), and edges define the flow between them.

### The Graph

![Agent Flowchart](docs/agent_flowchart.png)

- **Blue nodes** = shared setup steps (every message goes through these)
- **Orange diamond** = the conditional routing decision
- **Purple nodes** = the food logging pipeline (the main feature)
- **Teal nodes** = simple single-step handlers
- **Green node** = onboarding flow
- **Red node** = error/unknown intent fallback

### How Routing Works

Intent detection uses a **two-tier strategy** to minimize API costs:

1. **Keyword matching** (free, instant) -- checks the message against predefined keyword lists. Short keywords (<=3 chars like "hi") use word-boundary matching to avoid false positives (e.g., "hi" inside "chicken"). Query phrases like "what did I eat" are checked first to prevent them from matching as `log_food`.

2. **Gemini AI** (API call) -- only invoked when keyword matching fails. The AI classifies the intent with conversation history for better context.

### Detailed Food Logging Pipeline

![Nutrition Pipeline](docs/nutrition_pipeline.png)

The food logging pipeline has 3 stages:

1. **parse_food** -- Gemini AI extracts structured food items (name, quantity, unit, meal type) from the user's natural language message. Conversation history is passed for context (e.g., if user said "and a coffee" referring to a previous meal).
2. **lookup_nutrition** -- For each item, checks the persistent MySQL cache first; if not cached, searches USDA; caches the result; if USDA has no match, asks AI to estimate; if AI also fails, marks as unknown (0 cal).
3. **store_food_log** -- If all items are unknown, asks the user for help instead of saving. Otherwise saves to MySQL, calculates daily totals, and builds a formatted Slack response with emojis and a progress bar.

### State Object

Every node reads from and writes to a shared `ConversationState` dictionary:

```python
class ConversationState(TypedDict):
    user_id: str                          # Slack user ID
    team_id: str                          # Slack workspace ID
    message: str                          # Original user message
    intent: Optional[str]                 # Detected intent (log_food, greeting, etc.)
    user_context: Optional[Dict]          # User's profile (calorie goal, onboard status)
    history: Optional[list]               # Recent conversation messages for context
    parsed_foods: Optional[list]          # AI-parsed food items
    enriched_foods: Optional[list]        # Foods with nutrition data added
    totals: Optional[Dict[str, float]]    # Sum of calories, protein, carbs, fat
    response: Optional[str]              # Final message to send back to Slack
    error: Optional[str]                 # Error message if something went wrong
```

### Intent Routing

After the Router Agent classifies the message, the orchestrator routes to the right handler:

| Intent | Routes To | What It Does |
|--------|-----------|-------------|
| `log_food` | parse_food -> lookup_nutrition -> store_food_log | Full food logging pipeline |
| `query_today` | handle_query | Shows daily summary with progress bar and food items |
| `query_history` | handle_query | Shows historical summary with per-day food breakdown |
| `greeting` | handle_greeting | Says hi, prompts to log food |
| `help` | handle_help | Shows usage instructions |
| `onboarding_needed` | handle_onboarding | Collects user profile (age, weight, etc.) |
| `other` / `error` | handle_error | Generic fallback message |

---

## File-by-File Breakdown

### `src/main.py` - Entry Point

This is where the bot starts. It does 4 things:

1. **Validates config** - checks all API keys are present in `.env`
2. **Initializes database** - creates tables if they don't exist
3. **Sets up Slack event handlers** - registers 4 listeners:
   - `@app.event("message")` - handles DMs to the bot
   - `@app.event("app_mention")` - handles @CalorieBot mentions in channels
   - `@app.command("/calorie")` - handles the `/calorie` slash command
   - `@app.event("app_home_opened")` - shows a welcome screen in the App Home tab
4. **Starts Socket Mode** - keeps a persistent WebSocket connection to Slack (no public URL needed)

Every event handler follows the same pattern: extract `user_id`, `team_id`, and `text`, pass them to `orchestrator.process_message()`, and `say()` the response.

### `src/config.py` - Configuration

Uses **pydantic-settings** to load environment variables from `.env` into a typed `Settings` object. Required fields:
- `GOOGLE_API_KEY` - for Gemini AI
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET` - for Slack
- `DATABASE_URL` - MySQL connection string

Optional:
- `USDA_API_KEY` - for higher USDA rate limits
- `GEMINI_MODEL` - defaults to `gemini-1.5-flash`
- `DEBUG`, `LOG_LEVEL`, `ENVIRONMENT`, `TIMEZONE`

### `src/agents/orchestrator.py` - The Brain

The central coordinator. Contains:
- The LangGraph workflow definition (nodes + edges)
- All node handler functions (`_parse_food`, `_store_food_log`, `_handle_onboarding`, etc.)
- The `process_message()` method that main.py calls
- **Rate limiter** (10 requests/minute per user)
- **Date parsing** for historical queries ("yesterday", "last week", specific dates like "Feb 14")
- **Conversation history** save/load for context awareness

### `src/agents/router_agent.py` - Intent Classifier

Takes a message and returns what the user wants to do. Three-step process:
1. If the user hasn't completed onboarding, **always** routes to `onboarding_needed`
2. Attempts **keyword matching** against predefined intent lists (free, no API call):
   - Query phrases ("what did I eat") are checked first to avoid false `log_food` matches
   - Short keywords use word-boundary matching (prevents "hi" matching inside "chicken")
   - Keywords cover: query_today, query_history, help, greeting, log_food
3. If no keyword match, sends the message + conversation history to **Gemini AI** for classification

### `src/agents/food_parser.py` - NLU for Food

Takes "I had 2 eggs and toast" and returns structured data. Uses Gemini AI with a detailed system prompt that:
- Knows about standard serving sizes ("an apple" = 1 medium)
- Infers meal types from time of day
- Returns standardized units (never uses the food name as a unit)
- Receives conversation history for context (e.g., follow-up messages)

### `src/agents/nutrition_lookup.py` - Nutrition Data

For each parsed food item, this agent:
1. Searches the USDA FoodData Central API
2. Takes the best match
3. Scales nutrition from "per 100g" to the user's actual serving
4. If USDA has no match: asks Gemini AI to estimate
5. If AI also fails: marks as "unknown" (0 calories) and asks user for help

### `src/agents/storage_agent.py` - Database Operations

All database reads and writes go through this agent. Key operations:
- `get_or_create_user()` - find or make a user record
- `update_user()` - save profile changes (after onboarding)
- `create_food_log()` - store a meal entry
- `get_food_logs_by_date()` - retrieve all logs for a specific date (including items JSON)
- `get_food_logs_by_range()` - retrieve logs across a date range
- `get_daily_totals()` - sum up a day's calories, protein, carbs, fat
- `get_range_totals()` - sum nutrition across a date range with per-day breakdown and food names
- `delete_food_log()` - remove an entry
- `save_message()` - store a conversation message (auto-prunes to last 10)
- `get_recent_messages()` - fetch recent messages for conversation context

All methods return **plain dictionaries** (not ORM objects) to avoid SQLAlchemy session issues.

### `src/services/ai_service.py` - Gemini AI Wrapper

Wraps all interactions with Google Gemini. Three methods:
- `parse_food_message()` - extracts food items from text (returns JSON), accepts conversation history
- `detect_intent()` - classifies user intent (returns JSON), accepts conversation history
- `generate_response()` - generates natural language replies

Uses `response_mime_type="application/json"` to force Gemini to return valid JSON. Also strips markdown code fences that Gemini sometimes wraps around JSON.

Temperature is set to 0.3 (low) for consistent, predictable responses.

### `src/services/usda_service.py` - USDA API Wrapper

Wraps the USDA FoodData Central API. Key features:
- **Persistent MySQL cache** - stores USDA results in the `nutrition_cache` table so repeated lookups for the same food never hit the API again (survives bot restarts)
- **Nutrient parsing** - extracts calories, protein, carbs, fat, fiber, sugar from raw API response (matches by nutrient ID for reliability)
- **Serving size conversion** - maps 70+ unit names (cup, slice, egg, handful, nacho...) to gram weights, then scales nutrition accordingly

### `src/database/models.py` - ORM Models

Five SQLAlchemy models:

- **User** - one row per Slack user
- **FoodLog** - one row per meal logged
- **Goal** - one row per fitness goal (created during onboarding)
- **ConversationMessage** - stores recent user/bot messages per user for conversation context
- **NutritionCache** - persistent cache for USDA API responses

### `src/database/database.py` - Connection Management

Manages the SQLAlchemy engine and provides `get_db_session()` -- a context manager that auto-commits on success and auto-rolls back on error.

### `src/utils/calculations.py` - Health Math

Pure math functions with no dependencies:
- `calculate_bmr()` - Basal Metabolic Rate (Mifflin-St Jeor equation)
- `calculate_tdee()` - Total Daily Energy Expenditure (BMR x activity multiplier)
- `calculate_calorie_goal()` - TDEE adjusted for goal (e.g., -500 cal/day for weight loss)

### `src/utils/formatters.py` - Slack Message Formatting

Builds the formatted messages the bot sends back. Uses Slack's `mrkdwn` syntax (not standard markdown):
- `*bold*` instead of `**bold**`
- `_italic_` instead of `*italic*`
- `:emoji_name:` shortcodes instead of Unicode emojis

Key formatters:
- `format_food_log_message()` - formats a newly logged meal with per-item details
- `format_daily_summary()` - shows a single day's intake with progress bar, macros, and **food names under each meal**
- `format_range_summary()` - shows multi-day summaries with per-day calorie totals and **food eaten each day**
- `create_progress_bar()` - colored square emojis for visual progress

### `src/utils/rate_limiter.py` - Rate Limiting

Implements a per-user **sliding window** rate limiter (token bucket pattern):
- Default: 10 messages per 60-second window
- In-memory (resets on bot restart)
- Returns how many seconds until the user can send again
- Prevents abuse and excessive Gemini API costs

---

## Database Design

### Tables

#### `users`
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| slack_user_id | VARCHAR(50) | Unique Slack user ID (e.g., `U05XXXXXXX`) |
| slack_team_id | VARCHAR(50) | Slack workspace ID |
| age | INT | User's age |
| gender | VARCHAR(10) | "male" or "female" |
| current_weight | FLOAT | Weight in kg |
| target_weight | FLOAT | Goal weight in kg |
| height | FLOAT | Height in cm |
| activity_level | ENUM | sedentary / lightly_active / moderately_active / very_active / extra_active |
| daily_calorie_goal | INT | Calculated from TDEE + goal adjustment |
| preferences | JSON | Flexible key-value store |
| onboarded_at | DATETIME | NULL until onboarding is complete |
| is_active | BOOLEAN | Soft delete flag |
| created_at | DATETIME | When the user first messaged the bot |
| updated_at | DATETIME | Last profile change |

#### `food_logs`
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| user_id | INT (FK -> users.id) | Which user logged this |
| logged_at | DATETIME | When the meal was logged |
| meal_type | ENUM | breakfast / lunch / dinner / snack / other |
| raw_text | TEXT | Original message (e.g., "I had 2 eggs and toast") |
| items | JSON | Array of parsed food items with nutrition data |
| total_calories | FLOAT | Sum of all items' calories |
| total_protein | FLOAT | Sum of protein (grams) |
| total_carbs | FLOAT | Sum of carbs (grams) |
| total_fat | FLOAT | Sum of fat (grams) |
| confidence_score | FLOAT | How confident the parsing was (0-1) |
| created_at | DATETIME | Record creation time |
| updated_at | DATETIME | Last modification |

The `items` JSON column stores the full detail of each food item:
```json
[
  {
    "name": "scrambled eggs",
    "quantity": 2,
    "unit": "large",
    "calories": 148,
    "protein": 9.99,
    "carbs": 1.61,
    "fat": 11.09,
    "source": "usda",
    "fdc_id": 173424,
    "usda_match": "Egg, whole, cooked, scrambled",
    "confidence": "high"
  }
]
```

#### `goals`
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| user_id | INT (FK -> users.id) | Which user's goal |
| goal_type | ENUM | lose_weight / maintain_weight / gain_weight / build_muscle / general_health |
| status | ENUM | active / completed / abandoned |
| starting_weight | FLOAT | Weight when goal was created |
| target_weight | FLOAT | Target weight |
| current_weight | FLOAT | Latest weight |
| start_date | DATETIME | When goal started |
| target_date | DATETIME | Deadline (optional) |

#### `conversation_history`
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| user_id | INT (FK -> users.id) | Which user's message |
| role | VARCHAR(10) | "user" or "bot" |
| content | TEXT | The message text |
| created_at | DATETIME | When the message was sent |

Auto-pruned to keep only the **last 10 messages** per user. Used to provide conversation context to Gemini AI for better intent detection and food parsing.

#### `nutrition_cache`
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| cache_key | VARCHAR(255) | Unique key (e.g., `search:eggs:5`) |
| data | JSON | Cached API response |
| created_at | DATETIME | When the cache entry was created |

Persistent cache for USDA API responses. Survives bot restarts. Prevents redundant API calls when the same food is looked up multiple times.

### Relationships

```
User (1) ---< (many) FoodLog
User (1) ---< (many) Goal
User (1) ---< (many) ConversationMessage
```

A user has many food logs, goals, and conversation messages. Deleting a user cascades and deletes their logs and goals.

---

## Phase 2 Features

These features were added after the initial MVP to improve reliability, reduce API costs, and make conversations feel more natural.

### 1. Conversation Memory

**What**: The bot remembers the last 5 messages in a conversation to provide context.

**How**: After every message exchange, both the user's message and the bot's response are saved to the `conversation_history` table. When processing a new message, recent history is loaded and passed to Gemini AI alongside the current message.

**Why**: Enables follow-up messages like "and a coffee" after logging breakfast, and helps the AI understand ambiguous messages in context.

### 2. Keyword Matching for Intents

**What**: Common intents are detected via keyword matching *before* calling Gemini AI.

**How**: The router agent has predefined keyword lists for each intent. Messages are checked against these lists first. Only when no keyword match is found does the bot call Gemini for intent classification.

**Why**: Reduces Gemini API calls by ~60-70%. Most messages ("I had an apple", "what did I eat today?", "hi") match keywords and never need an AI call for intent detection.

**Special handling**:
- Query phrases ("what did I eat") are checked before log_food to prevent false matches on shared keywords like "ate"
- Short keywords (<=3 chars) use regex word boundaries to prevent matching inside other words (e.g., "hi" inside "chicken")

### 3. Date Parsing for Historical Queries

**What**: Users can ask about specific dates or date ranges using natural language.

**How**: The orchestrator's `_parse_date_reference()` method handles:
- Relative dates: "yesterday", "last week", "this week", "last 3 days"
- Specific dates: "Feb 14", "13th February 2026", "2026-02-14"
- Falls back to "today" if no date reference is found

Uses `dateutil.parser` for fuzzy date parsing of specific dates.

**Example queries**:
- "What did I eat yesterday?" -> shows single-day summary
- "Show me last week" -> shows 7-day summary with per-day breakdown
- "What did I eat on Feb 14?" -> shows that specific date's meals and food items

### 4. Persistent USDA Cache

**What**: USDA API responses are cached in MySQL instead of in-memory.

**How**: The `nutrition_cache` table stores serialized API responses keyed by search query. Before making a USDA API call, the cache is checked. Results are stored after successful API calls.

**Why**: Survives bot restarts (in-memory cache was lost on every restart). Eliminates redundant API calls across sessions. Common foods like "rice" or "chicken" are looked up once and cached permanently.

### 5. Per-User Rate Limiting

**What**: Each user is limited to 10 messages per 60-second window.

**How**: A sliding window token bucket tracks timestamps of each user's messages. If the limit is exceeded, the bot responds with a "slow down" message and tells the user how many seconds to wait.

**Why**: Prevents accidental API cost spikes (e.g., a user spamming messages) and protects Gemini's rate limits from being exhausted.

### 6. Food Summaries in Queries

**What**: When users ask "what did I eat?", the response now includes the actual food names, not just calorie totals.

**How**: The `items` JSON from each food log is parsed to extract food names. For single-day queries, food names appear under each meal. For multi-day queries, food names appear under each day.

**Example output (single day)**:
```
Daily Summary - Feb 14, 2026

1665/1562 calories (106%)
103 calories over

Meals logged:
  Breakfast: 305 cal
    mixed berries, greek yogurt, banana
  Lunch: 760 cal
    chole (chickpea curry), bhature
  Dinner: 600 cal
    pasta with marinara, garlic bread
```

**Example output (multi-day)**:
```
Last 7 Days (7 days)

Total: 10389 cal
Daily avg: 1484 cal

Per-day breakdown:
  Thu, Feb 12: 1360 cal
    oatmeal, banana, honey, grilled chicken breast, ...
  Fri, Feb 13: 1712 cal
    boiled eggs, whole wheat toast, paneer butter masala, ...
```

---

## Multi-User Support

The bot is fully multi-user. Here's how:

1. **User identification**: Every Slack message contains a unique `user_id` (e.g., `U05ABC123`). This is the primary key for identifying users.

2. **Automatic registration**: The first time any user messages the bot, `storage_agent.get_or_create_user()` creates a new row in the `users` table. No sign-up required.

3. **Per-user data**: Every food log is linked to a `user_id`. When User A asks "what did I eat today?", the query filters by their `user_id` -- they never see User B's data.

4. **Per-user goals**: Each user has their own calorie goal, calculated from their personal profile (age, weight, height, activity level, fitness goal).

5. **Per-user conversation history**: Each user's conversation context is stored and retrieved independently.

6. **Per-user rate limiting**: Rate limits are tracked per user, so one user's activity doesn't affect another.

7. **Team awareness**: The `slack_team_id` is stored too, so the same bot instance could theoretically serve multiple Slack workspaces (each user is identified by the combination of user_id + team_id).

8. **No shared state**: All agents are stateless. The `ConversationState` is created fresh for each message. User data comes from the database, not from in-memory state.

---

## How Users Access the Bot

There are **3 ways** users can interact with CalorieBot:

### 1. Direct Message (Primary)
Users open a DM with the bot and type naturally:
```
User: I had a chicken salad for lunch
Bot:  [formatted response with calories, macros, daily progress]
```
This is handled by `@app.event("message")` which filters for `channel_type == "im"`.

### 2. @Mention in Channels
In any channel where the bot is invited, users can mention it:
```
User: @CalorieBot I had a banana
Bot:  [responds in a thread]
```
This is handled by `@app.event("app_mention")`. The response is sent as a thread reply to avoid cluttering the channel.

### 3. Slash Command
Users can type `/calorie` followed by their message:
```
/calorie I had 2 eggs for breakfast
/calorie what did I eat today?
/calorie help
```
This is handled by `@app.command("/calorie")`. If no text is provided, it defaults to "help".

### 4. App Home Tab
When users click on the bot's name in Slack and open the "Home" tab, they see a welcome screen with quick start instructions. This is handled by `@app.event("app_home_opened")`.

---

## External APIs

### Google Gemini (AI)
- **What for**: Intent detection (fallback), food parsing, nutrition estimation, onboarding data extraction
- **Model**: Configurable via `GEMINI_MODEL` in `.env` (currently `gemini-2.5-flash-lite`)
- **Cost**: Free tier available (rate-limited; `gemini-2.5-flash-lite` has the most generous free quota)
- **Calls per message**: 0-3 depending on intent:
  - 0 calls if keyword matching handles intent + food was previously cached
  - 1 call for food parsing (most common)
  - 2-3 calls if AI intent detection is needed or USDA misses and AI estimates nutrition

### USDA FoodData Central
- **What for**: Accurate nutrition data (calories, protein, carbs, fat, fiber, sugar per 100g)
- **Cost**: 100% free
- **API key**: Optional (higher rate limits with key)
- **Data types queried**: Survey (FNDDS), Foundation, SR Legacy
- **Caching**: Results cached in MySQL `nutrition_cache` table (persistent across restarts)

### Slack Bolt
- **Connection**: Socket Mode (WebSocket) -- no public URL or ngrok needed
- **Events subscribed**: `message.im`, `app_mention`, `app_home_opened`
- **Scopes needed**: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`

---

## Nutrition Lookup Pipeline

When the bot needs to find nutrition data for a food item, it follows a 4-tier strategy:

```
Tier 0: Persistent MySQL Cache (instant, free)
   |
   | Not in cache?
   v
Tier 1: USDA Database (most accurate)
   |
   | Not found?
   v
Tier 2: Gemini AI Estimation (reasonable estimate)
   |
   | AI doesn't know either?
   v
Tier 3: Mark as "unknown" (0 cal) and ask the user for help
```

### Tier 0 - Persistent Cache
- Checks the `nutrition_cache` MySQL table for a previous lookup
- Key format: `search:<food_name>:<page_size>` or `food:<fdc_id>`
- Cache entries survive bot restarts

### Tier 1 - USDA Lookup
- Searches USDA FoodData Central by food name
- Takes the first (best) match
- USDA returns nutrition per 100g
- The bot converts the user's serving to grams using a unit mapping table (70+ units)
- Scales nutrition proportionally
- **Result is cached** in MySQL for future lookups

### Tier 2 - AI Estimation
- Asks Gemini: "Estimate nutrition for 2 large scrambled eggs"
- AI returns calories, protein, carbs, fat
- Tagged as `source: "ai_estimated"` so the user knows it's an estimate
- Response includes a note: "nutrition was estimated by AI"

### Tier 3 - Unknown
- Tagged as `confidence: "unknown"`, calories set to 0
- If ALL items in a message are unknown: bot asks user to rephrase or provide calories manually
- If SOME items are unknown: bot logs the known ones and warns about the unknown ones

---

## Onboarding Flow

New users must complete onboarding before they can log food. Here's the flow:

1. **User sends any message** -> Router detects `is_onboarded == False` -> routes to `handle_onboarding`

2. **First visit** -> Bot shows welcome message asking for: age, gender, weight, height, activity level, and goal

3. **User provides info** (e.g., "I'm 25, female, 60kg, 165cm, moderately active, want to lose weight")
   - Gemini AI extracts structured data from the message
   - Bot calculates:
     - **BMR** using Mifflin-St Jeor: `10 x weight + 6.25 x height - 5 x age - 161` (female)
     - **TDEE**: BMR x 1.55 (moderately active)
     - **Calorie goal**: TDEE - 500 (lose weight = 500 cal deficit)
   - Saves profile to database
   - Sets `onboarded_at` to now (marks as onboarded)
   - Shows personalized plan

4. **From now on**, the router lets their messages through to the normal intent flow.

### Calorie Goal Calculation Example

```
25-year-old female, 60kg, 165cm, moderately active, lose weight:

BMR = 10(60) + 6.25(165) - 5(25) - 161 = 600 + 1031.25 - 125 - 161 = 1345.25
TDEE = 1345.25 x 1.55 = 2085 cal/day (maintenance)
Goal = 2085 - 500 = 1585 cal/day (to lose ~0.5 kg/week)
```

---

## Configuration & Environment

All config is loaded from `.env` via pydantic-settings. The `Settings` class validates types and provides defaults.

### Required Variables
```
GOOGLE_API_KEY=...          # From https://aistudio.google.com/app/apikey
SLACK_BOT_TOKEN=xoxb-...   # From Slack app OAuth page
SLACK_APP_TOKEN=xapp-...   # From Slack app Socket Mode page
SLACK_SIGNING_SECRET=...    # From Slack app Basic Information page
DATABASE_URL=mysql+pymysql://user:pass@host/dbname
```

### Optional Variables
```
GEMINI_MODEL=gemini-2.5-flash-lite   # Which Gemini model to use
USDA_API_KEY=...                     # For higher USDA rate limits
ENVIRONMENT=development              # development or production
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR
DEBUG=False                          # Enables SQLAlchemy query logging
TIMEZONE=UTC                         # Application timezone
```

---

## Singleton Pattern

Most services and agents use the **singleton pattern** -- a single instance is created on first use and reused for all subsequent calls:

```python
_ai_service: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
```

This applies to: `AIService`, `USDAService`, `RouterAgent`, `FoodParserAgent`, `NutritionAgent`, `StorageAgent`, `CalorieBotOrchestrator`, and `Settings`.

Why: These objects hold API clients, database connections, and the LangGraph compiled graph -- all of which are expensive to create and should be reused.

---

## Logging

The bot logs to two places simultaneously:
- **Console** (`sys.stdout`) - for real-time monitoring
- **File** (`calorie_bot.log`) - for persistent history

Log format: `2026-02-04 20:15:30 - src.agents.orchestrator - INFO - Routed to intent: log_food`

Key events that are logged:
- Configuration validation (pass/fail)
- Database initialization
- Every incoming message (user ID + text)
- Intent detection results (keyword match vs Gemini)
- Food parsing results (number of items, confidence)
- USDA search results (number of matches, cache hit/miss)
- AI estimation attempts
- Rate limit rejections
- Conversation history saves
- Errors with full stack traces

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| **LangGraph** over simple if/else | Makes the conversation flow visual and extensible. Easy to add new intents/nodes. |
| **Google Gemini** over OpenAI | Free tier available. No credit card required to start. |
| **USDA API** over other nutrition APIs | Free, government-maintained, no sign-up required. Most accurate data. |
| **AI fallback** for unknown foods | USDA doesn't have everything (e.g., regional dishes). AI provides reasonable estimates. |
| **Keyword matching before AI** | Reduces Gemini API calls by ~60-70%. Most common intents are detectable by simple keywords. |
| **Word-boundary matching for short keywords** | Prevents false positives like "hi" matching inside "chicken". |
| **Persistent MySQL cache** over in-memory | Survives bot restarts. Common foods are cached once and never looked up again. |
| **Conversation memory** (last 5 messages) | Enables follow-up messages and contextual understanding without storing full history. |
| **Per-user rate limiting** | Prevents API cost spikes and protects Gemini rate limits from being exhausted. |
| **Socket Mode** over webhooks | No need for a public URL or ngrok. Works behind firewalls. Just run the script. |
| **MySQL** over SQLite | Better for multi-user production use. SQLite is still supported via config. |
| **Dict returns** from StorageAgent | SQLAlchemy ORM objects detach from sessions after the `with` block closes. Returning dicts avoids `DetachedInstanceError`. |
| **Slack mrkdwn** not standard markdown | Slack uses its own formatting syntax. `*bold*` not `**bold**`, `:emoji:` not Unicode. |
| **Singleton agents** | Avoids recreating API clients and compiled graphs on every message. |
| **Food names in query responses** | Users asking "what did I eat?" want to see actual foods, not just calorie numbers. |
| **All values rounded to 2 decimal places** | Prevents ugly output like `2.7222222222222223g`. |
| **Minimum 1200 cal goal** | Safety check -- the bot won't recommend dangerously low calorie intake. |
