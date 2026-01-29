import requests
import json
import os
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DB_FILE = "seen_hacks.json"

# --- BROWSERS HEADERS (To bypass security) ---
# Ye headers server ko convince karte hain ki hum Human hain
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com"
}

# Specific headers for JSON APIs
API_HEADERS = HEADERS.copy()
API_HEADERS["Accept"] = "application/json, text/plain, */*"

# --- CRAWLERS ---

def fetch_unstop():
    print("🔎 Checking Unstop...")
    url = "https://unstop.com/api/public/opportunity/search-result"
    payload = {"opportunity": "hackathons", "filters": "open_for_registration", "page": 1}
    
    try:
        # Unstop specific referer needed
        local_headers = API_HEADERS.copy()
        local_headers["Referer"] = "https://unstop.com/hackathons"
        
        r = requests.get(url, params=payload, headers=local_headers)
        
        if r.status_code != 200:
            print(f"⚠️ Unstop Blocked: Status {r.status_code}")
            return []
            
        data = r.json()
        hacks = data.get('data', {}).get('data', [])
        results = []
        for h in hacks:
            if h.get('regnRequirements', {}).get('remainingDays', 0) > 0:
                results.append({
                    "id": f"unstop_{h['id']}",
                    "text": f"🚀 *{h['title']}* (Unstop)\n🔗 https://unstop.com/{h['slug']}"
                })
        return results
    except Exception as e:
        print(f"❌ Unstop Error: {e}")
        return []

def fetch_devfolio():
    print("🔎 Checking Devfolio...")
    url = "https://api.devfolio.co/api/search/hackathons"
    payload = {"type": "offline", "filter": "open", "page": 0, "limit": 20}
    
    try:
        # Devfolio is strict about Origin
        local_headers = API_HEADERS.copy()
        local_headers["Origin"] = "https://devfolio.co"
        local_headers["Referer"] = "https://devfolio.co/"
        
        r = requests.post(url, json=payload, headers=local_headers)
        
        if r.status_code != 200:
            print(f"⚠️ Devfolio Blocked: Status {r.status_code}")
            return []

        data = r.json()
        results = []
        for h in data.get('result', []):
            results.append({
                "id": f"devfolio_{h['slug']}",
                "text": f"🛠 *{h['name']}* (Devfolio)\n🔗 https://{h['slug']}.devfolio.co"
            })
        return results
    except Exception as e:
        print(f"❌ Devfolio Error: {e}")
        return []

def fetch_devpost():
    print("🔎 Checking Devpost...")
    url = "https://devpost.com/hackathons?orderBy=submission-deadline&challenge_type[]=is_open"
    try:
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, 'html.parser')
        tiles = soup.find_all('div', class_='hackathon-tile')
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
        print(f"❌ Devpost Error: {e}")
        return []

def fetch_mlh():
    print("🔎 Checking MLH (Major League Hacking)...")
    # MLH uses year-based URLs. 2026 season url:
    url = "https://mlh.io/seasons/2026/events" 
    try:
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, 'html.parser')
        events = soup.find_all('div', class_='event-wrapper')
        results = []
        for event in events:
            title_tag = event.find('h3', class_='event-name')
            if not title_tag: continue
            title = title_tag.text.strip()
            link_tag = event.find('a', class_='event-link', href=True)
            link = link_tag['href'] if link_tag else "https://mlh.io"
            
            # Create a unique ID from the link
            results.append({
                "id": f"mlh_{link}",
                "text": f"🎓 *{title}* (MLH)\n🔗 {link}"
            })
        return results
    except Exception as e:
        print(f"❌ MLH Error: {e}")
        return []

# --- MAIN LOGIC ---

async def run_bot():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Secrets missing. Checking local hardcoded variables for testing...")
        # For local testing only. Remove before pushing if you want.
    
    # 1. Load History
    seen_ids = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                content = f.read()
                if content:
                    seen_ids = json.loads(content)
        except json.JSONDecodeError:
            seen_ids = []

    # 2. Aggregate Data from ALL sources
    all_hacks = []
    all_hacks += fetch_unstop()
    all_hacks += fetch_devfolio()
    all_hacks += fetch_devpost()
    all_hacks += fetch_mlh() # New Source Added
    
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
                # Wait 1 sec to avoid spamming Telegram API
                await asyncio.sleep(1) 
            except Exception as e:
                print(f"Failed to send: {e}")
        
        # 4. Save History
        with open(DB_FILE, 'w') as f:
            json.dump(seen_ids, f)
    else:
        print("😴 No new hackathons found.")

if __name__ == "__main__":
    asyncio.run(run_bot())