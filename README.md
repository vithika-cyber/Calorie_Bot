# CalorieBot - Slack Nutrition Tracker

A conversational AI-powered calorie tracking bot for Slack. Tell it what you ate in plain English and it handles the rest.

## Features

- **Natural Language Input** - "Had 2 eggs and toast for breakfast"
- **USDA Nutrition Data** - Accurate values from the official government database, with AI fallback estimation
- **Daily Tracking** - Progress bars, macro breakdowns, and goal tracking
- **Personalized Goals** - Calorie targets based on your age, weight, height, and activity level
- **Historical Queries** - "What did I eat yesterday?" or "Show me last week" with full food summaries
- **Conversation Memory** - Understands follow-up messages using recent chat context
- **Smart Routing** - Keyword matching reduces AI calls by ~60-70%; Gemini used only when needed
- **Persistent Caching** - USDA results cached in MySQL so repeated lookups are instant
- **Rate Limiting** - Per-user limits (10 msg/min) to prevent API abuse

## Architecture

Built with LangGraph (agentic workflow):

```
Slack message -> Rate Limiter -> Load Context + History
                                        |
                                   Router Agent
                              (keywords first, then AI)
                                        |
                    ┌───────────┬───────┼───────┬──────────┐
                    v           v       v       v          v
               Log Food     Query   Greeting  Help    Onboarding
                    |       (today/
                    v       history)
              Food Parser
             (Gemini AI)
                    |
                    v
           Nutrition Lookup
       (Cache -> USDA -> AI fallback)
                    |
                    v
           Storage Agent (MySQL)
                    |
                    v
           Formatted Response
         (with emojis + progress bar)
```

## Tech Stack

- **Python 3.11+** with LangGraph / LangChain
- **Google Gemini** for NLU (food parsing, intent detection, onboarding)
- **USDA FoodData Central API** for nutrition data
- **MySQL** via SQLAlchemy (5 tables: users, food_logs, goals, conversation_history, nutrition_cache)
- **Slack Bolt** with Socket Mode

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Get API keys

- **Google Gemini**: https://aistudio.google.com/app/apikey
- **USDA** (optional): https://fdc.nal.usda.gov/api-key-signup.html
- **Slack App**: Create at https://api.slack.com/apps
  - Enable Socket Mode, get App Token (`xapp-...`)
  - Add bot scopes: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`
  - Subscribe to events: `app_mention`, `message.im`
  - Install to workspace, get Bot Token (`xoxb-...`) and Signing Secret

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
GOOGLE_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash-lite
USDA_API_KEY=your-usda-key
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=your-secret
DATABASE_URL=mysql+pymysql://root:password@localhost/calorie_bot
```

### 4. Set up MySQL

```sql
CREATE DATABASE calorie_bot;
```

Tables are created automatically on first run.

### 5. Run

```bash
python -m src.main
```

DM the bot in Slack to start!

## Project Structure

```
src/
  main.py                 # Entry point, Slack event handlers
  config.py               # Settings from .env
  agents/
    orchestrator.py       # LangGraph workflow (core logic + date parsing + rate limiting)
    router_agent.py       # Intent classification (keyword match + Gemini fallback)
    food_parser.py        # NL -> structured food data (with conversation context)
    nutrition_lookup.py   # USDA lookup + AI fallback
    storage_agent.py      # Database CRUD + conversation history + range queries
  services/
    ai_service.py         # Google Gemini wrapper (with history support)
    usda_service.py       # USDA FoodData Central wrapper (with persistent MySQL cache)
  database/
    database.py           # SQLAlchemy engine/session
    models.py             # User, FoodLog, Goal, ConversationMessage, NutritionCache
  utils/
    calculations.py       # BMR, TDEE, calorie goal math
    formatters.py         # Slack message formatting (daily summary, range summary, food logs)
    rate_limiter.py       # Per-user sliding window rate limiter
```

## Example Interactions

**Logging food:**
```
User: I had 2 eggs and toast for breakfast
Bot:  ✅ Logged Breakfast (8:30 AM)
      🥚 2 large scrambled eggs: 148 cal | P: 9.99g C: 1.61g F: 11.09g
      🍞 1 slice toast: 75 cal | P: 2.6g C: 14.3g F: 1.0g
      Meal total: 223 calories
      📊 Daily Progress: 223/1562 cal (14%)
```

**Querying a specific date:**
```
User: What did I eat on Feb 14?
Bot:  📊 Daily Summary - Feb 14, 2026
      1665/1562 calories (106%)
      Meals logged:
        🌅 Breakfast: 305 cal
          mixed berries, greek yogurt, banana
        ☀️ Lunch: 760 cal
          chole (chickpea curry), bhature
        🌙 Dinner: 600 cal
          pasta with marinara, garlic bread
```

**Querying a date range:**
```
User: What did I eat last week?
Bot:  📅 Last 7 Days (7 days)
      Total: 10389 cal | Daily avg: 1484 cal
      Per-day breakdown:
        Thu, Feb 12: 1360 cal
          oatmeal, banana, grilled chicken breast, dal, rice, roti
        Fri, Feb 13: 1712 cal
          boiled eggs, toast, paneer butter masala, naan, chicken stir fry
        ...
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot doesn't respond | Check Socket Mode is on, tokens are correct, bot is installed |
| Gemini quota error (429) | Switch to `gemini-2.5-flash-lite` in `.env`, or wait for daily reset |
| USDA returns no results | Bot falls back to AI estimation automatically |
| Database errors | Verify `DATABASE_URL` and that the MySQL database exists |
| "Slow down" message | Rate limit hit (10 msg/min). Wait a few seconds. |

## Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system guide including database schema, agent design, and all design decisions.

## License

MIT
