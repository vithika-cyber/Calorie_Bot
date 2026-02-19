# Calorie Counting Slack Bot 🥗

A conversational AI-powered calorie tracking bot for Slack that makes nutrition logging feel natural and effortless.

## Features

- 🗣️ **Natural Language Processing**: Just tell the bot what you ate - "Had 2 eggs and toast for breakfast"
- 🤖 **Agentic AI System**: Built with LangGraph for intelligent conversation flow
- 📊 **Real-time Tracking**: See your daily progress and macro breakdown instantly
- 🎯 **Personalized Goals**: Set targets based on your fitness objectives
- 🔍 **USDA Nutrition Data**: Accurate nutrition information from official government database
- 💾 **Complete History**: Track your eating patterns over time

## Architecture

This bot uses an agentic system powered by LangGraph with multiple specialized agents:

- **Router Agent**: Determines user intent (logging food, asking questions, etc.)
- **Food Parser Agent**: Extracts structured data from natural language using GPT-4
- **Nutrition Agent**: Looks up accurate nutrition data from USDA API
- **Storage Agent**: Manages all database operations
- **Query Agent**: Handles questions about your food history

## Prerequisites

- Python 3.11 or higher
- OpenAI API key (GPT-4 access)
- Slack workspace with admin permissions
- USDA API key (optional but recommended)

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
cd count_calories
pip install -r requirements.txt
```

### 2. Get API Keys

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-proj-...`)

#### USDA API Key (Optional)
1. Go to https://fdc.nal.usda.gov/api-key-signup.html
2. Sign up for a free API key
3. Copy the key from your email

#### Slack App Setup
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it (e.g., "CalorieBot") and select your workspace

**Enable Socket Mode:**
- Go to "Socket Mode" in sidebar
- Toggle "Enable Socket Mode" ON
- Create a token (name: "Local Dev")
- Copy the App Token (starts with `xapp-`)

**Add Bot Token Scopes:**
Go to "OAuth & Permissions" → "Bot Token Scopes", add:
- `app_mentions:read`
- `chat:write`
- `im:history`
- `im:read`
- `im:write`
- `users:read`

**Subscribe to Events:**
- Go to "Event Subscriptions"
- Toggle "Enable Events" ON
- Add bot events: `app_mention`, `message.im`

**Install to Workspace:**
- Go to "Install App"
- Click "Install to Workspace"
- Copy the Bot User OAuth Token (starts with `xoxb-`)

**Get Signing Secret:**
- Go to "Basic Information"
- Under "App Credentials", copy the Signing Secret

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
OPENAI_API_KEY=sk-proj-your-actual-key
USDA_API_KEY=your-usda-key-optional
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
```

### 4. Run the Bot

```bash
python src/main.py
```

You should see:
```
⚡️ Bolt app is running!
🤖 CalorieBot is online and ready!
```

### 5. Test in Slack

Open Slack and DM the bot:
```
"Hi!"
```

The bot will guide you through onboarding and help you start tracking!

## Usage Examples

### Logging Food

**Simple:**
```
"I had an apple"
"Ate a banana"
```

**Complex:**
```
"Had 2 scrambled eggs, whole wheat toast with avocado, and coffee for breakfast"
"Lunch was a chicken caesar salad with grilled chicken breast"
```

**With Time Context:**
```
"This morning I had oatmeal with blueberries"
"Yesterday evening I had pizza"
```

### Asking Questions

```
"What did I eat today?"
"Show my breakfast"
"How many calories so far?"
"What's my daily goal?"
"Show me yesterday's meals"
```

### Corrections

```
"Actually that was 3 eggs, not 2"
"Delete my last entry"
"That was a large apple, not medium"
```

## How It Works

1. **You send a message** in natural language
2. **Router Agent** determines your intent
3. **Food Parser Agent** extracts food items using GPT-4
4. **Nutrition Agent** looks up data from USDA database
5. **Storage Agent** saves to your personal log
6. **Bot responds** with a summary and your daily progress

## Project Structure

```
count_calories/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── agents/              # LangGraph agents
│   ├── services/            # API wrappers
│   ├── database/            # Database models
│   └── utils/               # Helper functions
├── tests/                   # Unit tests
├── calories.db              # SQLite database (auto-created)
├── requirements.txt         # Python dependencies
└── .env                     # Your API keys
```

## Troubleshooting

### Bot doesn't respond in Slack
- Check that Socket Mode is enabled
- Verify SLACK_APP_TOKEN and SLACK_BOT_TOKEN are correct
- Make sure the bot is installed to your workspace
- Check the terminal for error messages

### "OpenAI API error"
- Verify your OPENAI_API_KEY is correct
- Check you have available credits: https://platform.openai.com/usage
- Ensure you have GPT-4 access

### "USDA API error" 
- The bot works without a USDA API key (but has rate limits)
- If you have a key, verify it's correctly set in `.env`
- Check internet connection

### Database errors
- Delete `calories.db` to reset the database
- Make sure you have write permissions in the directory

## API Costs Estimate

**OpenAI API (GPT-4):**
- ~$0.01-0.03 per food logging interaction
- ~$5-15/month for moderate daily use

**USDA API:**
- 100% free (with optional API key for higher limits)

**Slack:**
- Free for standard workspace

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black src/
```

### Database Reset
```bash
rm calories.db
python src/main.py  # Will recreate on startup
```

## Roadmap

- [ ] Photo-based food logging (GPT-4 Vision)
- [ ] Exercise tracking and calorie adjustment
- [ ] Weekly insights and pattern analysis
- [ ] Custom foods and recipes
- [ ] Integration with fitness apps (Strava, Apple Health)
- [ ] Web dashboard for visualizations
- [ ] Multi-language support

## Contributing

This is a personal project, but suggestions and feedback are welcome!

## License

MIT License - Feel free to use and modify for your own projects.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the terminal logs for error messages
3. Verify all API keys are correctly configured

---

Built with ❤️ using LangGraph, OpenAI GPT-4, and USDA FoodData Central
