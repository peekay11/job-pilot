import asyncio
import os
import json
import random
import csv
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from openai import AsyncOpenAI

load_dotenv()

CONFIG_PATH = "config.json"
CSV_PATH = "job_applications_tracker.csv"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def log_application(company, title, url):
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Company", "Job Title", "URL"])
        writer.writerow([datetime.now().isoformat(), company, title, url])

LLM_CACHE = {}

async def ask_llm(question, context, job_desc=""):
    if question in LLM_CACHE:
        return LLM_CACHE[question]
        
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("\n[ERROR] No API key found. Please ensure your .env file contains OPENROUTER_API_KEY=your_key_here\n")
        raise RuntimeError("Missing OpenRouter API Key")
        
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    prompt = f"""
Candidate Profile Context:
{json.dumps(context, indent=2)}

Job Description Context:
{job_desc[:3000]}

The application asks the following screening question:
"{question}"

Based on the profile and job description, provide the answer to the question.
CRITICAL RULES:
1. OUTPUT ONLY THE EXACT RAW TEXT TO BE TYPED. Do NOT include phrases like "Based on the candidate's profile" or "I would answer". NO quotes, NO prefixes.
2. If the question asks for "years of experience" (or any numeric value), YOU MUST OUTPUT ONLY A RAW NUMBER (e.g., "0", "1", "3").
   - If the skill is relevant to Software Engineering (e.g., C#, Java, Python, AWS), NEVER answer 0. Output at least "1".
   - If the skill/industry is COMPLETELY unrelated (e.g., Gambling, Casinos, Arabic), BE HONEST and output strictly "0".
   - NEVER output text like "years" or explanations (e.g., never say "0, but I have..."). ONLY THE DIGIT.
3. If the question asks for a salary, hourly rate, or daily rate, provide a realistic raw number based on the candidate's profile (e.g., "50" for hourly USD, "400" for daily EUR). ALWAYS favor the candidate by aiming for the higher end of the market rate—do not lowball. NEVER answer "N/A" for compensation questions!
4. NEVER return an empty string. Default to "N/A" (or "1" for numeric) if absolutely trapped.
5. If a list of Options is provided in the prompt, you MUST return EXACTLY one of those options verbatim. Do not invent an option like "None". If you lack the skill, pick the lowest tier option provided in the exact list.
"""
    retries = 3
    for attempt in range(retries):
        try:
            completion = await client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct",
                messages=[
                    {"role": "system", "content": "You are a strict data-entry bot. You output ONLY the exact string to be typed into a form field. You never use conversational filler, prefixes, or quotes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
            )
            ans = completion.choices[0].message.content.strip()
            if ans: 
                LLM_CACHE[question] = ans
                return ans
        except Exception as e:
            print(f"Error calling OpenRouter API (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    raise RuntimeError("CRITICAL: OpenRouter API failed after 3 retries. Aborting script to protect application quality!")

async def fill_form_fields(page, config, job_desc=""):
    await asyncio.sleep(2)
    
    modal = page.locator("div[role='dialog']")
    if await modal.count() == 0:
        return
        
    candidate = config.get("candidate_profile", {})
    
    # 1. Text, Email, Tel, Number, Textarea
    inputs = await modal.first.locator("input[type='text'], input[type='email'], input[type='tel'], input[type='number'], textarea").all()
    
    for input_field in inputs:
        if not await input_field.is_visible(): continue
        
        # Skip if already filled
        try:
            current_val = await input_field.input_value(timeout=1000)
            if current_val and current_val.strip() != "":
                continue
        except Exception:
            pass
            
        input_id = await input_field.get_attribute("id")
        label_text = ""
        if input_id:
            label = page.locator(f"label[for='{input_id}']")
            if await label.count() > 0:
                label_text = await label.first.inner_text()
        
        if not label_text:
            label_text = await input_field.get_attribute("aria-label") or await input_field.get_attribute("placeholder") or ""
            
        if not label_text: continue
        label_lower = label_text.lower()
        
        value_to_fill = ""
        if "first name" in label_lower: value_to_fill = candidate.get("first_name", "")
        elif "last name" in label_lower: value_to_fill = candidate.get("last_name", "")
        elif "email" in label_lower: value_to_fill = candidate.get("email", "")
        elif "phone" in label_lower or "mobile" in label_lower: value_to_fill = candidate.get("phone", "")
        elif "city" in label_lower or "location" in label_lower: value_to_fill = candidate.get("location", "")
        else:
            value_to_fill = await ask_llm(label_text, candidate, job_desc)
            print(f"🤖 [OpenRouter] Q: '{label_text}'\n   => A: '{value_to_fill}'")
            
        if value_to_fill:
            try:
                await input_field.fill(value_to_fill, timeout=5000)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"Failed to fill text field '{label_text}': {e}")

    # 2. Radio buttons / Yes-No Questions (usually inside fieldsets)
    fieldsets = await modal.first.locator("fieldset").all()
    for fs in fieldsets:
        if not await fs.is_visible(): continue
        
        legend_loc = fs.locator("legend")
        if await legend_loc.count() == 0: continue
        legend_text = await legend_loc.first.inner_text()
        
        # Check if already answered
        radios = await fs.locator("input[type='radio']").all()
        already_selected = False
        for r in radios:
            try:
                if await r.is_checked(timeout=1000):
                    already_selected = True
                    break
            except: pass
        if already_selected: continue
        
        labels = await fs.locator("label").all()
        options = []
        for l in labels:
            try: options.append((await l.inner_text()).strip())
            except: pass
            
        if not options: continue
        
        question = f"{legend_text} (Options: {', '.join(options)})"
        answer = await ask_llm(f"{question}\nReturn EXACTLY one of the provided options, nothing else.", candidate, job_desc)
        print(f"🤖 [OpenRouter] Q: '{legend_text}'\n   => A: '{answer}'")
        
        for l in labels:
            try:
                if (await l.inner_text()).strip().lower() == answer.lower() or answer.lower() in (await l.inner_text()).strip().lower():
                    await l.click(timeout=5000)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    break
            except Exception: pass

    # 3. Select Dropdowns
    selects = await modal.first.locator("select").all()
    for sel in selects:
        if not await sel.is_visible(): continue
        
        input_id = await sel.get_attribute("id")
        label_text = await sel.get_attribute("aria-label") or ""
        if input_id:
            label = page.locator(f"label[for='{input_id}']")
            if await label.count() > 0:
                label_text = await label.first.inner_text()
                
        if not label_text: continue
        
        options_loc = await sel.locator("option").all()
        options = []
        for o in options_loc:
            try:
                text = (await o.inner_text()).strip()
                if text and text.lower() != "select an option":
                    options.append(text)
            except: pass
            
        if not options: continue
        
        label_lower = label_text.lower()
        answer = ""
        
        # Local Hardcodes for Dropdowns
        if "email" in label_lower:
            for opt in options:
                if candidate.get("email", "").lower() in opt.lower():
                    answer = opt
                    break
            if not answer and options: answer = options[0]
            
        elif "country code" in label_lower:
            for opt in options:
                if "+27" in opt or "South Africa" in opt:
                    answer = opt
                    break
                    
        if answer:
            print(f"⚡ [HARDCODED] Q: '{label_text}'\n   => A: '{answer}'")
        else:
            question = f"{label_text} (Options: {', '.join(options)})"
            answer = await ask_llm(f"{question}\nReturn EXACTLY one of the provided options, nothing else.", candidate, job_desc)
            print(f"🤖 [OpenRouter] Q: '{label_text}'\n   => A: '{answer}'")
        
        try:
            await sel.select_option(label=answer, timeout=5000)
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception: pass

    # 4. Checkboxes (e.g., "I agree to terms", "Acknowledge")
    checkboxes = await modal.first.locator("input[type='checkbox']").all()
    for cb in checkboxes:
        try:
            if await cb.is_visible(timeout=1000) and not await cb.is_checked():
                print("=> Found an unchecked checkbox, attempting to check it.")
                # Force=True because sometimes the actual input is visually hidden behind a custom label
                await cb.check(force=True, timeout=2000)
                await asyncio.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass

async def process_job(page, job_card, config):
    try:
        await job_card.scroll_into_view_if_needed(timeout=5000)
        await job_card.click(timeout=5000)
    except Exception as e:
        print(f"Failed to click job card: {e}")
        return False
        
    # Wait for right panel to load
    await asyncio.sleep(random.uniform(*config['delay_range']))
    
    # Extract Job Description to feed to AI
    job_desc = ""
    try:
        desc_loc = page.locator(".jobs-description__container, #job-details")
        if await desc_loc.count() > 0:
            job_desc = await desc_loc.first.inner_text()
    except Exception: pass
    
    easy_apply_button = page.get_by_role("button", name="Easy Apply")
    if await easy_apply_button.count() == 0:
        easy_apply_button = page.get_by_label("Easy Apply to this job")
        
    if await easy_apply_button.count() == 0:
        print("=> No Easy Apply button found. Skipping (might be an external redirect).")
        return False
        
    try:
        await easy_apply_button.first.click(timeout=5000)
    except Exception as e:
        print(f"=> Failed to click Easy Apply: {e}")
        return False
        
    await asyncio.sleep(random.uniform(*config['delay_range']))
    
    print("\nProcessing Application Modal...")
    
    while True:
        await fill_form_fields(page, config, job_desc)
        
        modal = page.locator("div[role='dialog'], [data-test-id='dialog-content']")
        if await modal.count() == 0:
            print("=> Modal not found or closed unexpectedly.")
            break
            
        # Look for Submit
        submit_button = modal.get_by_role("button", name="Submit application")
        if await submit_button.count() > 0 and await submit_button.first.is_visible():
            print("=> Found 'Submit application' button. Ready to submit.")
            break
            
        # Look for Review
        review_button = modal.get_by_role("button", name="Review")
        if await review_button.count() > 0 and await review_button.first.is_visible():
            print("=> Found 'Review' button. Clicking...")
            try:
                await review_button.first.click(timeout=5000)
                await asyncio.sleep(random.uniform(*config['delay_range']))
                continue
            except Exception as e:
                print(f"   [!] Failed to click Review: {e}")
                break
            
        # Look for Next
        next_button = modal.get_by_role("button", name="Next")
        if await next_button.count() > 0 and await next_button.first.is_visible():
            print("=> Found 'Next' button. Clicking...")
            try:
                await next_button.first.click(timeout=5000)
                await asyncio.sleep(random.uniform(*config['delay_range']))
                continue
            except Exception as e:
                print(f"   [!] Failed to click Next: {e}")
                break
            
        print("=> No 'Next', 'Review', or 'Submit' buttons found. Stopping modal traversal.")
        break
        
    company = "Unknown Company"
    title = "Unknown Title"
    
    try:
        company_loc = page.locator(".job-details-jobs-unified-top-card__company-name")
        if await company_loc.count() > 0:
            company = await company_loc.first.inner_text()
            
        title_loc = page.locator(".job-details-jobs-unified-top-card__job-title")
        if await title_loc.count() > 0:
            title = await title_loc.first.inner_text()
    except Exception:
        pass
        
    print(f"\n--- Submitting Application Automatically ---")
    print(f"Target: {title} @ {company}")
    
    modal = page.locator("div[role='dialog'], [data-test-id='dialog-content']")
    submit_button = modal.get_by_role("button", name="Submit application")
    
    if await submit_button.count() > 0 and await submit_button.first.is_visible():
        try:
            print("=> Clicking Submit Application...")
            await submit_button.first.click(timeout=5000)
            print("=> Application submitted successfully!")
            log_application(company, title, page.url)
            
            # Handle post-submit dialogs ("Your application was sent...")
            await asyncio.sleep(2)
            
            # 1. Try explicit buttons
            for btn_name in ["Done", "Not now", "Dismiss", "Close"]:
                cleanup_btn = modal.get_by_role("button", name=btn_name)
                if await cleanup_btn.count() > 0 and await cleanup_btn.first.is_visible():
                    try:
                        print(f"=> Clicking post-submit '{btn_name}' button.")
                        await cleanup_btn.first.click(timeout=5000)
                        await asyncio.sleep(1)
                        break
                    except Exception: pass
                    
            # 2. If modal still visible, try hitting 'Escape' or clicking the top-right X
            if await modal.count() > 0 and await modal.first.is_visible():
                print("=> Attempting generic modal dismiss...")
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(1)
                    dismiss_icon = modal.locator("button[aria-label='Dismiss'], button[data-test-modal-close-btn]")
                    if await dismiss_icon.count() > 0:
                        await dismiss_icon.first.click(timeout=2000)
                except Exception: pass
                
            return True
        except Exception as e:
            print(f"   [!] Failed to click submit: {e}")
            return False
    else:
        print("=> Submit button not found or visible. Skipping.")
        # Attempt to dismiss modal to keep state clean for next card
        try:
            dismiss_btn = modal.locator("button[aria-label='Dismiss'], button[data-test-modal-close-btn]")
            if await dismiss_btn.count() > 0 and await dismiss_btn.first.is_visible():
                print("=> Clicking Dismiss (X) button...")
                await dismiss_btn.first.click(timeout=5000)
                await asyncio.sleep(1)
                discard_btn = page.locator("button[data-control-name='discard_application_confirm_btn'], button:has-text('Discard')")
                if await discard_btn.count() > 0 and await discard_btn.first.is_visible():
                    print("=> Confirming Discard...")
                    await discard_btn.first.click(timeout=5000)
        except Exception as e:
            print(f"   [!] Failed to dismiss modal: {e}")
        return False


async def main():
    print("Starting AI-Powered Job Application Co-Pilot...")
    config = load_config()
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("WARNING: NO OPENROUTER_API_KEY FOUND IN .env FILE.")
        print("The bot will not be able to answer custom screening questions.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        await asyncio.sleep(3)
        
    async with async_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--start-maximized']
        )
        
        page = await browser.new_page()
        
        print(f"Navigating to Target Search URL...")
        await page.goto(config["search_url"])
        
        print("\nEnsure you are logged into the platform.")
        print("Waiting for job list to render...")
        
        try:
            await page.wait_for_selector(".job-card-container", timeout=60000)
        except Exception:
            print("Could not find job cards. Proceeding anyway...")
        
        applications_submitted = 0
        max_apps = config.get("max_applications", 20)
        
        while applications_submitted < max_apps:
            # Scroll the left job list pane to load all lazy-loaded cards
            job_list_panel = page.locator(".jobs-search-results-list")
            if await job_list_panel.count() > 0:
                print("Scrolling job list to load more cards...")
                for _ in range(5):
                    try:
                        await job_list_panel.first.evaluate("el => el.scrollBy(0, 1000)")
                        await asyncio.sleep(1.5)
                    except Exception:
                        pass
                        
            job_card_loc = page.locator(".job-card-container")
            count = await job_card_loc.count()
            print(f"Found {count} job cards on this page.")
            
            for index in range(count):
                if applications_submitted >= max_apps:
                    break
                    
                print(f"\nEvaluating Job Card {index + 1}/{count}...")
                
                # Re-fetch the locator dynamically by index
                card = job_card_loc.nth(index)
                
                try:
                    # Quick optimization: check if the card already has the "Applied" badge
                    card_text = await card.inner_text()
                    if "Applied" in card_text:
                        print("=> Already applied to this job. Skipping.")
                        continue
                except Exception:
                    pass
                    
                try:
                    success = await asyncio.wait_for(process_job(page, card, config), timeout=180.0)
                except asyncio.TimeoutError:
                    print("=> [!] FATAL: Job processing HUNG (exceeded 3 minutes)! Forcing timeout and moving to the next card.")
                    success = False
                except Exception as e:
                    print(f"=> [!] Unexpected error processing job: {e}")
                    success = False
                if success:
                    applications_submitted += 1
                    
                delay = random.uniform(5, 10) 
                print(f"Sleeping for {delay:.2f} seconds before next action...")
                await asyncio.sleep(delay)
                
            if applications_submitted >= max_apps:
                print(f"Reached volume cap of {max_apps} applications.")
                break
                
            # Attempt to navigate to the next page of search results
            next_page_btn = page.locator("button[aria-label='View next page']")
            if await next_page_btn.count() > 0 and await next_page_btn.first.is_visible():
                print("\n=> Moving to next page of search results...")
                try:
                    await next_page_btn.first.click(timeout=5000)
                    await asyncio.sleep(random.uniform(5, 8))
                except Exception as e:
                    print(f"=> Failed to click Next Page: {e}")
                    break
            else:
                print("=> No more pages found. Ending session.")
                break
                
        print(f"\nSession Complete. Submitted {applications_submitted} applications.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
