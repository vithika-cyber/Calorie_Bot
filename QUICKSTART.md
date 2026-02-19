# Quick Start Guide

Get your CalorieBot up and running in 5 minutes!

## Prerequisites

- Python 3.11 or higher
- Slack workspace where you can create apps
- OpenAI API key

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Get Your API Keys

### OpenAI API Key (Required)

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-...`)

### Slack App Setup (Required)

1. **Create App**: https://api.slack.com/apps → "Create New App" → "From scratch"
2. **Name it**: e.g., "CalorieBot"
3. **Select your workspace**

4. **Enable Socket Mode**:
   - Go to "Socket Mode" in sidebar
   - Toggle ON
   - Create token (name: "Local Dev")
   - Copy the App Token (starts with `xapp-`)

5. **Add Bot Scopes**:
   - Go to "OAuth & Permissions"
   - Under "Bot Token Scopes", add:
     - `app_mentions:read`
     - `chat:write`
     - `im:history`
     - `im:read`
     - `im:write`
     - `users:read`

6. **Subscribe to Events**:
   - Go to "Event Subscriptions"
   - Toggle ON
   - Add bot events:
     - `app_mention`
     - `message.im`

7. **Install to Workspace**:
   - Go to "Install App"
   - Click "Install to Workspace"
   - Copy the Bot Token (starts with `xoxb-`)

8. **Get Signing Secret**:
   - Go to "Basic Information"
   - Copy the "Signing Secret"

### USDA API Key (Optional)

Without a key, you get basic access. With a key, you get higher rate limits:

1. Go to https://fdc.nal.usda.gov/api-key-signup.html
2. Sign up (free)
3. Copy the API key from your email

## Step 3: Configure Environment

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```env
OPENAI_API_KEY=sk-proj-your-key-here
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_APP_TOKEN=xapp-your-token-here
SLACK_SIGNING_SECRET=your-secret-here
USDA_API_KEY=your-key-here-optional
```

## Step 4: Run the Bot

```bash
python src/main.py
```

You should see:

```
⚡️ Bolt app is running!
🤖 CalorieBot is online and ready!
```

## Step 5: Test It!

1. Open Slack
2. Find CalorieBot in Apps
3. Send it a DM: `Hi!`
4. Follow the onboarding prompts
5. Try logging food: `I had 2 eggs and toast for breakfast`

## Common Commands

**Logging food:**
- "I had a chicken salad for lunch"
- "Ate a banana"
- "Had coffee with milk"

**Checking progress:**
- "What did I eat today?"
- "How many calories so far?"
- "Show my meals"

**Getting help:**
- "help"
- "how does this work?"

## Troubleshooting

### Bot doesn't respond
- Check that Socket Mode is enabled in Slack app settings
- Verify SLACK_APP_TOKEN and SLACK_BOT_TOKEN are correct
- Make sure the bot is installed to your workspace

### "OpenAI API error"
- Verify OPENAI_API_KEY is correct
- Check you have credits: https://platform.openai.com/usage
- Ensure you have GPT-4 access

### "Database error"
- Delete `calories.db` and restart
- Check you have write permissions in the directory

## Next Steps

- Customize your calorie goal
- Explore weekly summaries
- Try logging complex meals
- Set up weight goals

## Need Help?

Check the main README.md for detailed documentation and troubleshooting.

Enjoy tracking your nutrition! 🥗
