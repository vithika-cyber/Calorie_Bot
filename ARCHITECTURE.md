# CalorieBot - Complete Architecture & System Guide

## Table of Contents

1. [What This Project Is](#what-this-project-is)
2. [How It Works (End to End)](#how-it-works-end-to-end)
3. [Project Structure](#project-structure)
4. [The Agent System (LangGraph)](#the-agent-system-langgraph)
5. [File-by-File Breakdown](#file-by-file-breakdown)
6. [Database Design](#database-design)
7. [Multi-User Support](#multi-user-support)
8. [How Users Access the Bot](#how-users-access-the-bot)
9. [External APIs](#external-apis)
10. [Nutrition Lookup Pipeline](#nutrition-lookup-pipeline)
11. [Onboarding Flow](#onboarding-flow)
12. [Configuration & Environment](#configuration--environment)
13. [Singleton Pattern](#singleton-pattern)
14. [Logging](#logging)
15. [Key Design Decisions](#key-design-decisions)

---

## What This Project Is

CalorieBot is a Slack chatbot that lets users track what they eat using natural language. Instead of manually looking up calories and entering numbers, a user just types something like *"I had 2 eggs and toast for breakfast"* and the bot:

1. Understands what foods were mentioned (using Google Gemini AI)
2. Looks up accurate nutrition data (from the USDA government database)
3. Stores everything in a MySQL database (per user)
4. Responds with a formatted summary showing calories, macros, and daily progress

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
[Step 1: get_user_context]
    - Looks up or creates the user in MySQL
    - Checks if they've completed onboarding
    - Gets their calorie goal (default 2000 if not set)
        |
        v
[Step 2: route_intent]
    - Sends message to Gemini AI: "Classify this message's intent"
    - AI returns: { intent: "log_food", confidence: "high" }
    - If user is NOT onboarded, all messages route to onboarding instead
        |
        v
[Step 3: parse_food] (because intent = "log_food")
    - Sends message to Gemini AI with a detailed prompt
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
      1. Search USDA FoodData Central API for "scrambled eggs"
      2. Get nutrition per 100g (e.g., 148 cal, 9.99g protein, ...)
      3. Convert to the user's serving size (2 large eggs = 2 x 50g = 100g)
      4. Scale the nutrition: 148 cal for 100g
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
  
  src/
    __init__.py             # Package marker, contains version
    main.py                 # Entry point: Slack event handlers, bot startup
    config.py               # Loads .env into a Settings object (pydantic)
    
    agents/                 # The "brain" - AI agents that process messages
      __init__.py
      orchestrator.py       # LangGraph workflow that coordinates everything
      router_agent.py       # Classifies user intent (log_food, query, greeting...)
      food_parser.py        # Extracts structured food data from natural language
      nutrition_lookup.py   # Looks up calories/macros from USDA + AI fallback
      storage_agent.py      # All database read/write operations
    
    services/               # Wrappers for external APIs
      __init__.py
      ai_service.py         # Google Gemini API wrapper (food parsing, intent detection)
      usda_service.py       # USDA FoodData Central API wrapper (nutrition data)
    
    database/               # Database layer
      __init__.py
      database.py           # SQLAlchemy engine, session management
      models.py             # ORM models: User, FoodLog, Goal
    
    utils/                  # Pure helper functions (no API calls, no DB)
      __init__.py
      calculations.py       # BMR, TDEE, calorie goal math
      formatters.py         # Builds Slack-formatted response messages
  
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

### Detailed Food Logging Pipeline

![Nutrition Pipeline](docs/nutrition_pipeline.png)

The food logging pipeline has 3 stages:

1. **parse_food** -- Gemini AI extracts structured food items (name, quantity, unit, meal type) from the user's natural language message
2. **lookup_nutrition** -- For each item, searches USDA first; if not found, asks AI to estimate; if AI also fails, marks as unknown (0 cal)
3. **store_food_log** -- If all items are unknown, asks the user for help instead of saving. Otherwise saves to MySQL, calculates daily totals, and builds a formatted Slack response with emojis and a progress bar

### State Object

Every node reads from and writes to a shared `ConversationState` dictionary:

```python
class ConversationState(TypedDict):
    user_id: str                          # Slack user ID
    team_id: str                          # Slack workspace ID
    message: str                          # Original user message
    intent: Optional[str]                 # Detected intent (log_food, greeting, etc.)
    user_context: Optional[Dict]          # User's profile (calorie goal, onboard status)
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
| `query_today` | handle_query | Shows daily summary with progress bar |
| `query_history` | handle_query | Shows past meal history |
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

This is the longest file because it contains the actual business logic for each conversation path.

### `src/agents/router_agent.py` - Intent Classifier

Takes a message and returns what the user wants to do. Two-step process:
1. If the user hasn't completed onboarding, **always** routes to `onboarding_needed` (regardless of what they said)
2. Otherwise, sends the message to Gemini AI for intent classification

### `src/agents/food_parser.py` - NLU for Food

Takes "I had 2 eggs and toast" and returns structured data. Uses Gemini AI with a detailed system prompt that:
- Knows about standard serving sizes ("an apple" = 1 medium)
- Infers meal types from time of day
- Returns standardized units (never uses the food name as a unit)

Also adds time-of-day context (morning = likely breakfast, evening = likely dinner).

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
- `get_food_logs_by_date()` - retrieve all logs for a specific date
- `get_daily_totals()` - sum up today's calories, protein, carbs, fat
- `delete_food_log()` - remove an entry

All methods return **plain dictionaries** (not ORM objects) to avoid SQLAlchemy session issues.

### `src/services/ai_service.py` - Gemini AI Wrapper

Wraps all interactions with Google Gemini. Three methods:
- `parse_food_message()` - extracts food items from text (returns JSON)
- `detect_intent()` - classifies user intent (returns JSON)
- `generate_response()` - generates natural language replies

Uses `response_mime_type="application/json"` to force Gemini to return valid JSON. Also strips markdown code fences that Gemini sometimes wraps around JSON.

Temperature is set to 0.3 (low) for consistent, predictable responses.

### `src/services/usda_service.py` - USDA API Wrapper

Wraps the USDA FoodData Central API. Key features:
- **24-hour in-memory cache** - avoids repeat API calls for the same food
- **Nutrient parsing** - extracts calories, protein, carbs, fat, fiber, sugar from raw API response (matches by nutrient ID for reliability)
- **Serving size conversion** - maps 70+ unit names (cup, slice, egg, handful, nacho...) to gram weights, then scales nutrition accordingly

### `src/database/models.py` - ORM Models

Three SQLAlchemy models:

- **User** - one row per Slack user
- **FoodLog** - one row per meal logged
- **Goal** - one row per fitness goal (currently created during onboarding)

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

Includes food-specific emojis (chicken = :poultry_leg:, apple = :apple:) and progress bars made of colored square emojis.

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

### Relationships

```
User (1) ---< (many) FoodLog
User (1) ---< (many) Goal
```

A user has many food logs and many goals. Deleting a user cascades and deletes their logs and goals.

---

## Multi-User Support

The bot is fully multi-user. Here's how:

1. **User identification**: Every Slack message contains a unique `user_id` (e.g., `U05ABC123`). This is the primary key for identifying users.

2. **Automatic registration**: The first time any user messages the bot, `storage_agent.get_or_create_user()` creates a new row in the `users` table. No sign-up required.

3. **Per-user data**: Every food log is linked to a `user_id`. When User A asks "what did I eat today?", the query filters by their `user_id` -- they never see User B's data.

4. **Per-user goals**: Each user has their own calorie goal, calculated from their personal profile (age, weight, height, activity level, fitness goal).

5. **Team awareness**: The `slack_team_id` is stored too, so the same bot instance could theoretically serve multiple Slack workspaces (each user is identified by the combination of user_id + team_id).

6. **No shared state**: All agents are stateless. The `ConversationState` is created fresh for each message. User data comes from the database, not from in-memory state.

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
- **What for**: Intent detection, food parsing, nutrition estimation, onboarding data extraction
- **Model**: Configurable via `GEMINI_MODEL` in `.env` (currently `gemini-2.5-flash-lite`)
- **Cost**: Free tier available (rate-limited; `gemini-2.5-flash-lite` has the most generous free quota)
- **Calls per message**: 1-3 depending on intent (intent detection always; food parsing if logging; nutrition estimation if USDA fails)

### USDA FoodData Central
- **What for**: Accurate nutrition data (calories, protein, carbs, fat, fiber, sugar per 100g)
- **Cost**: 100% free
- **API key**: Optional (higher rate limits with key)
- **Data types queried**: Survey (FNDDS), Foundation, SR Legacy
- **Caching**: Results cached in-memory for 24 hours to avoid repeat calls

### Slack Bolt
- **Connection**: Socket Mode (WebSocket) -- no public URL or ngrok needed
- **Events subscribed**: `message.im`, `app_mention`, `app_home_opened`
- **Scopes needed**: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`

---

## Nutrition Lookup Pipeline

When the bot needs to find nutrition data for a food item, it follows a 3-tier fallback strategy:

```
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

### Tier 1 - USDA Lookup
- Searches USDA FoodData Central by food name
- Takes the first (best) match
- USDA returns nutrition per 100g
- The bot converts the user's serving to grams using a unit mapping table (70+ units)
- Scales nutrition proportionally

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
- Intent detection results
- Food parsing results (number of items, confidence)
- USDA search results (number of matches)
- AI estimation attempts
- Errors with full stack traces

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| **LangGraph** over simple if/else | Makes the conversation flow visual and extensible. Easy to add new intents/nodes. |
| **Google Gemini** over OpenAI | Free tier available. No credit card required to start. |
| **USDA API** over other nutrition APIs | Free, government-maintained, no sign-up required. Most accurate data. |
| **AI fallback** for unknown foods | USDA doesn't have everything (e.g., regional dishes). AI provides reasonable estimates. |
| **Socket Mode** over webhooks | No need for a public URL or ngrok. Works behind firewalls. Just run the script. |
| **MySQL** over SQLite | Better for multi-user production use. SQLite is still supported via config. |
| **Dict returns** from StorageAgent | SQLAlchemy ORM objects detach from sessions after the `with` block closes. Returning dicts avoids `DetachedInstanceError`. |
| **Slack mrkdwn** not standard markdown | Slack uses its own formatting syntax. `*bold*` not `**bold**`, `:emoji:` not Unicode. |
| **Singleton agents** | Avoids recreating API clients and compiled graphs on every message. |
| **In-memory USDA cache** | Reduces API calls. Same food searched twice within 24h hits cache instead of USDA. |
| **All values rounded to 2 decimal places** | Prevents ugly output like `2.7222222222222223g`. |
| **Minimum 1200 cal goal** | Safety check -- the bot won't recommend dangerously low calorie intake. |
