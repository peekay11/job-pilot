# Job Pilot - AI-Powered Job Application Automation

An intelligent, fully-automated bot that applies to LinkedIn jobs on your behalf. It reads job descriptions live, tailors answers to screening questions using OpenRouter (Llama 3), and handles complex application modals so you can focus on interviewing.

## Features
- **Fully Automated Flow**: Navigates LinkedIn, parses job cards, handles multi-page application modals, and clicks submit.
- **Context-Aware AI**: Scrapes the "About the job" description and feeds it to an LLM alongside your profile so answers are perfectly tailored to the role.
- **Smart Form Parsing**: Hardcoded fast-paths for dropdowns (Country Code, Email) and AI processing for complex text, radio, and select inputs.
- **Anti-Hang Protection**: Global timeouts and strict post-submit modal destroyers keep the bot running cleanly in the background.

## Setup Instructions

### 1. Install Dependencies
Ensure you have Python 3.10+ installed.
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Profile
1. Copy the example configuration file:
   ```bash
   cp config.example.json config.json
   ```
2. Open `config.json` and enter your name, email, target LinkedIn search URL, resume summary, and salary expectations. The AI will use this profile to answer questions on your behalf.

### 3. Add Your AI Key (OpenRouter)
The bot uses OpenRouter to access Llama 3 for intelligent form filling.
1. Get a free API key from [OpenRouter.ai](https://openrouter.ai/)
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and paste your key: `OPENROUTER_API_KEY=sk-or-v1-...`

### 4. Run the Bot
```bash
python main.py
```
*Note: The script uses a local Chrome Profile stored in `./chrome_profile/`. The very first time you run the script, it will open a browser. You must manually log into your LinkedIn account. Once logged in, the bot takes over. Subsequent runs will stay logged in automatically.*

### Tracker
Successfully submitted applications are logged into `job_applications_tracker.csv`.
