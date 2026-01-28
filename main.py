import requests
import json
import os
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot

# --- CONFIGURATION ---
# We get these from GitHub Secrets later. 
# locally, you can hardcode them to test, but DO NOT commit keys to GitHub.
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
CHAT_ID = os.environ.get("CHAT_ID")
DB_FILE = "seen_hacks.json"

# --- CRAWLERS ---

def fetch_unstop():
    print("🔎 Checking Unstop...")
    url = "https://unstop.com/api/public/opportunity/search-result"
    payload = {"opportunity": "hackathons", "filters": "open_for_registration", "page": 1}
    try:
        r = requests.get(url, params=payload).json()
        hacks = r.get('data', {}).get('data', [])
        results = []
        for h in hacks:
            if h.get('regnRequirements', {}).get('remainingDays', 0) > 0:
                results.append({
                    "id": f"unstop_{h['id']}",
                    "text": f"🚀 *{h['title']}* (Unstop)\n🔗 https://unstop.com/{h['slug']}"
                })
        return results
    except Exception as e:
        print(f"Unstop Error: {e}")
        return []

def fetch_devfolio():
    print("🔎 Checking Devfolio...")
    url = "https://api.devfolio.co/api/search/hackathons"
    payload = {"type": "offline", "filter": "open", "page": 0, "limit": 20}
    try:
        r = requests.post(url, json=payload, headers={"Origin": "https://devfolio.co"}).json()
        results = []
        for h in r.get('result', []):
            results.append({
                "id": f"devfolio_{h['slug']}",
                "text": f"🛠 *{h['name']}* (Devfolio)\n🔗 https://{h['slug']}.devfolio.co"
            })
        return results
    except Exception as e:
        print(f"Devfolio Error: {e}")
        return []

def fetch_devpost():
    print("🔎 Checking Devpost...")
    url = "https://devpost.com/hackathons?orderBy=submission-deadline&challenge_type[]=is_open"
    try:
        soup = BeautifulSoup(requests.get(url).text, 'html.parser')
        tiles = soup.find_all('div', class_='hackathon-tile')
        results = []
        for tile in tiles:
            title = tile.find('h3', class_='mb-4').text.strip()
            link = tile.find('a', href=True)['href']
            # Use link as ID since Devpost doesn't expose a clean ID
            results.append({
                "id": f"devpost_{link}", 
                "text": f"🌍 *{title}* (Devpost)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"Devpost Error: {e}")
        return []

# --- MAIN LOGIC ---

async def run_bot():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: Bot Token or Chat ID missing.")
        return

    # 1. Load History
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            seen_ids = json.load(f)
    else:
        seen_ids = []

    # 2. Aggregate Data
    all_hacks = fetch_unstop() + fetch_devfolio() + fetch_devpost()
    
    new_hacks = []
    for hack in all_hacks:
        if hack['id'] not in seen_ids:
            new_hacks.append(hack)
            seen_ids.append(hack['id'])

    # 3. Send Notifications
    if new_hacks:
        bot = Bot(token=BOT_TOKEN)
        print(f"✅ Found {len(new_hacks)} new hackathons. Sending alerts...")
        
        for hack in new_hacks:
            try:
                await bot.send_message(chat_id=CHAT_ID, text=hack['text'], parse_mode='Markdown')
            except Exception as e:
                print(f"Failed to send: {e}")
        
        # 4. Save History (Crucial to avoid duplicates)
        with open(DB_FILE, 'w') as f:
            json.dump(seen_ids, f)
    else:
        print("😴 No new hackathons found.")

if __name__ == "__main__":
    asyncio.run(run_bot())