import cloudscraper
import json
import os
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DB_FILE = "seen_hacks.json"

# --- SCRAPER SETUP ---
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

# --- CRAWLERS ---

def fetch_unstop():
    print("🔎 Checking Unstop...")
    url = "https://unstop.com/api/public/opportunity/search-result"
    payload = {"opportunity": "hackathons", "filters": "open_for_registration", "page": 1}
    try:
        r = scraper.get(url, params=payload)
        data = r.json()
        hacks = data.get('data', {}).get('data', [])
        print(f"   ↳ Unstop found: {len(hacks)} items") # Debug Line
        return [{
            "id": f"unstop_{h['id']}",
            "text": f"🚀 *{h['title']}* (Unstop)\n🔗 https://unstop.com/{h['slug']}"
        } for h in hacks if h.get('regnRequirements', {}).get('remainingDays', 0) > 0]
    except Exception as e:
        print(f"❌ Unstop Error: {e}")
        return []

def fetch_devfolio():
    print("🔎 Checking Devfolio...")
    url = "https://api.devfolio.co/api/search/hackathons"
    payload = {"type": "offline", "filter": "open", "page": 0, "limit": 20}
    try:
        r = scraper.post(url, json=payload, headers={"Origin": "https://devfolio.co"})
        data = r.json()
        hacks = data.get('result', [])
        print(f"   ↳ Devfolio found: {len(hacks)} items")
        return [{
            "id": f"devfolio_{h['slug']}",
            "text": f"🛠 *{h['name']}* (Devfolio)\n🔗 https://{h['slug']}.devfolio.co"
        } for h in hacks]
    except Exception as e:
        print(f"❌ Devfolio Error: {e}")
        return []

def fetch_devpost():
    print("🔎 Checking Devpost...")
    url = "https://devpost.com/hackathons?orderBy=submission-deadline&challenge_type[]=is_open"
    try:
        r = scraper.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        tiles = soup.find_all('div', class_='hackathon-tile')
        print(f"   ↳ Devpost found: {len(tiles)} items")
        results = []
        for tile in tiles:
            title = tile.find('h3', class_='mb-4').text.strip()
            link = tile.find('a', href=True)['href']
            results.append({
                "id": f"devpost_{link}", 
                "text": f"🌍 *{title}* (Devpost)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"❌ Devpost Error: {e}")
        return []

def fetch_mlh():
    print("🔎 Checking MLH...")
    url = "https://mlh.io/seasons/2026/events"
    try:
        r = scraper.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        events = soup.find_all('div', class_='event-wrapper')
        print(f"   ↳ MLH found: {len(events)} items")
        results = []
        for event in events:
            title = event.find('h3', class_='event-name').text.strip()
            link = event.find('a', class_='event-link', href=True)['href']
            results.append({
                "id": f"mlh_{link}",
                "text": f"🎓 *{title}* (MLH)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"❌ MLH Error: {e}")
        return []

def fetch_dorahacks():
    print("🔎 Checking DoraHacks (Web3)...")
    url = "https://dorahacks.io/api/hackathon/list"
    try:
        r = scraper.get(url)
        data = r.json()
        # DoraHacks structure is diverse, we take the main list
        hacks = data.get('data', [])
        print(f"   ↳ DoraHacks found: {len(hacks)} items")
        results = []
        for h in hacks:
            # Only active ones
            if h.get('status') == 'UPCOMING' or h.get('status') == 'ONGOING':
                name = h.get('name', 'Unknown Hackathon')
                link = f"https://dorahacks.io/hackathon/{h.get('id')}"
                results.append({
                    "id": f"dora_{h['id']}",
                    "text": f"💰 *{name}* (DoraHacks)\n🔗 {link}"
                })
        return results
    except Exception as e:
        print(f"❌ DoraHacks Error: {e}")
        return []

def fetch_hackerearth():
    print("🔎 Checking HackerEarth (Jobs)...")
    url = "https://www.hackerearth.com/challenges/hackathon/"
    try:
        r = scraper.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        # HackerEarth uses 'challenge-card-modern' class
        cards = soup.find_all('div', class_='challenge-card-modern')
        print(f"   ↳ HackerEarth found: {len(cards)} items")
        results = []
        for card in cards:
            # Filter for "Live" or "Upcoming"
            status_tag = card.find('div', class_='status-label')
            if status_tag and ('Live' in status_tag.text or 'Upcoming' in status_tag.text):
                title = card.find('span', class_='challenge-list-title').text.strip()
                link = card.find('a', class_='challenge-card-link')['href']
                if not link.startswith('http'): link = f"https:{link}"
                results.append({
                    "id": f"he_{link}",
                    "text": f"💼 *{title}* (HackerEarth)\n🔗 {link}"
                })
        return results
    except Exception as e:
        print(f"❌ HackerEarth Error: {e}")
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
    all_hacks += fetch_dorahacks()     # NEW
    all_hacks += fetch_hackerearth()   # NEW
    
    new_hacks = []
    for hack in all_hacks:
        if hack['id'] not in seen_ids:
            new_hacks.append(hack)
            seen_ids.append(hack['id'])

    if new_hacks:
        bot = Bot(token=BOT_TOKEN)
        print(f"✅ Found {len(new_hacks)} NEW hackathons to send.")
        
        for hack in new_hacks:
            try:
                await bot.send_message(chat_id=CHAT_ID, text=hack['text'], parse_mode='Markdown')
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Failed to send: {e}")
        
        with open(DB_FILE, 'w') as f:
            json.dump(seen_ids, f)
    else:
        print("😴 No NEW hackathons found (Database is up to date).")

if __name__ == "__main__":
    asyncio.run(run_bot())