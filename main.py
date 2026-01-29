import cloudscraper
import requests # Standard requests for simple sites
import json
import os
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DB_FILE = "seen_hacks.json"

# --- 1. POWERFUL SCRAPER (For Unstop & Devfolio) ---
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

# --- 2. SIMPLE REQUESTS (For MLH & Devpost) ---
# Sometimes simple is better. These sites block complex TLS fingerprints.
def get_simple_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

# --- CRAWLERS ---

def fetch_unstop():
    print("🔎 Checking Unstop...")
    url = "https://unstop.com/api/public/opportunity/search-result"
    payload = {"opportunity": "hackathons", "filters": "open_for_registration", "page": 1}
    try:
        r = scraper.get(url, params=payload)
        data = r.json()
        hacks = data.get('data', {}).get('data', [])
        print(f"   ✅ Unstop: Found {len(hacks)} items")
        return [{
            "id": f"unstop_{h['id']}",
            "text": f"🚀 *{h['title']}* (Unstop)\n🔗 https://unstop.com/{h['slug']}"
        } for h in hacks if h.get('regnRequirements', {}).get('remainingDays', 0) > 0]
    except Exception as e:
        print(f"   ❌ Unstop Error: {e}")
        return []

def fetch_devfolio():
    print("🔎 Checking Devfolio...")
    url = "https://api.devfolio.co/api/search/hackathons"
    payload = {"type": "offline", "filter": "open", "page": 0, "limit": 20}
    # Headers are CRITICAL here
    headers = {
        "Origin": "https://devfolio.co",
        "Referer": "https://devfolio.co/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = scraper.post(url, json=payload, headers=headers)
        data = r.json()
        hacks = data.get('result', [])
        print(f"   ✅ Devfolio: Found {len(hacks)} items")
        return [{
            "id": f"devfolio_{h['slug']}",
            "text": f"🛠 *{h['name']}* (Devfolio)\n🔗 https://{h['slug']}.devfolio.co"
        } for h in hacks]
    except Exception as e:
        # Debugging: Print why it failed
        print(f"   ❌ Devfolio Failed. Status: {r.status_code}")
        return []

def fetch_devpost():
    print("🔎 Checking Devpost...")
    url = "https://devpost.com/hackathons?orderBy=submission-deadline&challenge_type[]=is_open"
    try:
        # Use Standard Requests (Not Scraper)
        r = requests.get(url, headers=get_simple_headers(), timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tiles = soup.find_all('div', class_='hackathon-tile')
        
        if len(tiles) == 0:
            print(f"   ⚠️ Devpost found 0. Page Title: {soup.title.string.strip() if soup.title else 'No Title'}")
        else:
            print(f"   ✅ Devpost: Found {len(tiles)} items")

        results = []
        for tile in tiles:
            title_tag = tile.find('h3', class_='mb-4')
            if title_tag:
                title = title_tag.text.strip()
                link = tile.find('a', href=True)['href']
                results.append({
                    "id": f"devpost_{link}", 
                    "text": f"🌍 *{title}* (Devpost)\n🔗 {link}"
                })
        return results
    except Exception as e:
        print(f"   ❌ Devpost Error: {e}")
        return []

def fetch_mlh():
    print("🔎 Checking MLH...")
    # Trying 2025 because 2026 might be empty or redirecting
    url = "https://mlh.io/seasons/2025/events" 
    try:
        # Use Standard Requests
        r = requests.get(url, headers=get_simple_headers(), timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        events = soup.find_all('div', class_='event-wrapper')
        
        if len(events) == 0:
            print(f"   ⚠️ MLH found 0. Page Title: {soup.title.string.strip() if soup.title else 'No Title'}")
        else:
            print(f"   ✅ MLH: Found {len(events)} items")

        results = []
        for event in events:
            title_tag = event.find('h3', class_='event-name')
            if not title_tag: continue
            title = title_tag.text.strip()
            link_tag = event.find('a', class_='event-link', href=True)
            link = link_tag['href'] if link_tag else "https://mlh.io"
            results.append({
                "id": f"mlh_{link}",
                "text": f"🎓 *{title}* (MLH)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"   ❌ MLH Error: {e}")
        return []

def fetch_dorahacks():
    print("🔎 Checking DoraHacks...")
    url = "https://dorahacks.io/api/hackathon/list"
    try:
        # DoraHacks needs simple headers too
        r = requests.get(url, headers=get_simple_headers(), timeout=10)
        data = r.json()
        hacks = data.get('data', [])
        
        # Filter Logic
        active_hacks = [h for h in hacks if h.get('status') in ['UPCOMING', 'ONGOING']]
        print(f"   ✅ DoraHacks: Found {len(active_hacks)} active items")
        
        results = []
        for h in active_hacks:
            name = h.get('name', 'Unknown Hackathon')
            link = f"https://dorahacks.io/hackathon/{h.get('id')}"
            results.append({
                "id": f"dora_{h['id']}",
                "text": f"💰 *{name}* (DoraHacks)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"   ❌ DoraHacks Error: {e}")
        return []

# --- MAIN LOGIC ---

async def run_bot():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Secrets missing.")
    
    seen_ids = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                content = f.read()
                if content: seen_ids = json.loads(content)
        except: seen_ids = []

    # Gather from ALL sources
    all_hacks = []
    all_hacks += fetch_unstop()
    all_hacks += fetch_devfolio()
    all_hacks += fetch_devpost()
    all_hacks += fetch_mlh()
    all_hacks += fetch_dorahacks()
    
    new_hacks = []
    for hack in all_hacks:
        if hack['id'] not in seen_ids:
            new_hacks.append(hack)
            seen_ids.append(hack['id'])

    if new_hacks:
        bot = Bot(token=BOT_TOKEN)
        print(f"🔥 Found {len(new_hacks)} NEW hackathons. Sending...")
        
        for hack in new_hacks:
            try:
                await bot.send_message(chat_id=CHAT_ID, text=hack['text'], parse_mode='Markdown')
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Failed to send: {e}")
        
        with open(DB_FILE, 'w') as f:
            json.dump(seen_ids, f)
    else:
        print("😴 No NEW hackathons found (DB Updated).")

if __name__ == "__main__":
    asyncio.run(run_bot())