# CalorieBot - Slack Nutrition Tracker

A conversational AI-powered calorie tracking bot for Slack. Tell it what you ate in plain English and it handles the rest.

## Features

- **Natural Language Input** - "Had 2 eggs and toast for breakfast"
- **USDA Nutrition Data** - Accurate values from the official government database, with AI fallback estimation
- **Daily Tracking** - Progress bars, macro breakdowns, and goal tracking
- **Personalized Goals** - Calorie targets based on your age, weight, height, and activity level

## Architecture

Built with LangGraph (agentic workflow):

```
Slack message -> Router Agent -> Food Parser (Gemini AI)
                                      |
                              Nutrition Lookup (USDA API + AI fallback)
                                      |
                              Storage Agent (MySQL) -> Response
```

## Tech Stack

- **Python 3.11+** with LangGraph / LangChain
- **Google Gemini** for NLU (food parsing, intent detection, onboarding)
- **USDA FoodData Central API** for nutrition data
- **MySQL** via SQLAlchemy
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
    orchestrator.py       # LangGraph workflow (core logic)
    router_agent.py       # Intent classification
    food_parser.py        # NL -> structured food data
    nutrition_lookup.py   # USDA lookup + AI fallback
    storage_agent.py      # Database CRUD
  services/
    ai_service.py         # Google Gemini wrapper
    usda_service.py       # USDA FoodData Central wrapper
  database/
    database.py           # SQLAlchemy engine/session
    models.py             # User, FoodLog, Goal models
  utils/
    calculations.py       # BMR, TDEE, calorie goal math
    formatters.py         # Slack message formatting
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot doesn't respond | Check Socket Mode is on, tokens are correct, bot is installed |
| Gemini quota error (429) | Switch to `gemini-2.5-flash-lite` in `.env`, or wait for daily reset |
| USDA returns no results | Bot falls back to AI estimation automatically |
| Database errors | Verify `DATABASE_URL` and that the MySQL database exists |

## License

MIT
