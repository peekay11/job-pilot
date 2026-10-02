import argparse
import sys
import os
import json
import asyncio
from .core import main as run_bot

def init_project():
    config_path = "config.json"
    env_path = ".env"
    
    if not os.path.exists(config_path):
        config_template = {
          "search_url": "https://www.linkedin.com/jobs/search/?f_AL=true&keywords=C%23%20OR%20.NET%20OR%20Java%20OR%20Fintech%20OR%20Backend",
          "candidate_profile": {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "123 456 7890",
            "email": "johndoe@example.com",
            "location": "Johannesburg, South Africa",
            "work_authorization": "Yes",
            "require_sponsorship": "No (for South Africa). Open to visa sponsorship for international relocation.",
            "resume_summary": "High-performance Backend Software Engineer specializing in scalable, high-availability systems for Fintech and Big Tech environments. Primary expertise in C# / .NET, alongside deep proficiency in Java, Python, and JavaScript/TypeScript. Experienced in low-latency backend architectures, RESTful API design, GCP, Cloudflare Workers, Docker, and CI/CD pipelines. Strong track record as a tech lead and mentor.",
            "location_preferences": "1. Cape Town (highly willing to relocate for tech hubs). 2. Johannesburg / Sandton (local, open to hybrid/on-site). 3. International Remote (fully equipped to work remotely from SA earning USD/EUR). 4. Global Relocation (open to visa sponsorship for high-earning tech hubs).",
            "career_goals": "Targeting high-earning Backend Engineering roles within Tier-1 Fintechs, Big Tech, and quantitative trading firms where I can leverage my C# and Java expertise to build mission-critical financial systems.",
            "salary_expectations": {
              "hourly_usd": "50",
              "daily_eur": "400",
              "annual_zar": "1000000"
            }
          },
          "max_applications": 20,
          "delay_range": [2, 5]
        }
        with open(config_path, "w") as f:
            json.dump(config_template, f, indent=2)
        print("✅ Created config.json")
    else:
        print("⚠️ config.json already exists. Skipping.")
        
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("OPENROUTER_API_KEY=your_openrouter_api_key_here\n")
        print("✅ Created .env")
    else:
        print("⚠️ .env already exists. Skipping.")
        
    print("\nInitialization complete! Edit config.json and .env, then run:")
    print("  job-pilot run")

def main():
    parser = argparse.ArgumentParser(description="Job Pilot: AI-Powered LinkedIn Application Automation")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("init", help="Initialize config.json and .env in the current directory")
    subparsers.add_parser("run", help="Start applying to jobs")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_project()
    elif args.command == "run":
        if not os.path.exists("config.json"):
            print("❌ Error: config.json not found! Run 'job-pilot init' first.")
            sys.exit(1)
        asyncio.run(run_bot())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
