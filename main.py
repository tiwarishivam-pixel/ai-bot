import cloudscraper
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

# --- SCRAPER SETUP ---
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

def get_simple_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        print(f"   ✅ Unstop Found: {len(hacks)}")
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
    # TRICK: "offline" hata diya, taaki online hacks bhi aayein
    payload = {"filter": "open", "page": 0, "limit": 20}
    headers = {
        "Origin": "https://devfolio.co",
        "Referer": "https://devfolio.co/",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        r = scraper.post(url, json=payload, headers=headers)
        data = r.json()
        hacks = data.get('result', [])
        print(f"   ✅ Devfolio Found: {len(hacks)}")
        return [{
            "id": f"devfolio_{h['slug']}",
            "text": f"🛠 *{h['name']}* (Devfolio)\n🔗 https://{h['slug']}.devfolio.co"
        } for h in hacks]
    except Exception as e:
        print(f"   ❌ Devfolio Error: {e}")
        return []

def fetch_devpost():
    print("🔎 Checking Devpost...")
    url = "https://devpost.com/hackathons?orderBy=submission-deadline&challenge_type[]=is_open"
    try:
        r = requests.get(url, headers=get_simple_headers(), timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Method 1: Try Tile
        tiles = soup.find_all('div', class_='hackathon-tile')
        # Method 2: Try Challenge Listing (Backup)
        if not tiles:
            tiles = soup.find_all('div', class_='challenge-listing')
            
        print(f"   ✅ Devpost Found: {len(tiles)}")

        results = []
        for tile in tiles:
            title_tag = tile.find('h3') or tile.find('h2')
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
    url = "https://mlh.io/seasons/2026/events"
    try:
        r = requests.get(url, headers=get_simple_headers(), timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        events = soup.find_all('div', class_='event-wrapper')
        print(f"   ✅ MLH Found: {len(events)}")
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
        print(f"   ❌ MLH Error: {e}")
        return []

# --- MAIN LOGIC ---

async def run_bot():
    print("🚀 Starting Hackathon Hunter...")
    
    # --- FORCE RESET (Jugaad) ---
    # Hum file load hi nahi karenge. Hum manenge ki humne aaj tak kuch nahi dekha.
    seen_ids = [] 
    print("⚠️ Memory Disabled: Sending ALL found hackathons!")

    # Fetch Data
    all_hacks = []
    all_hacks += fetch_unstop()
    all_hacks += fetch_devfolio()
    all_hacks += fetch_devpost()
    all_hacks += fetch_mlh()
    
    # Filter Logic (Ab ye saare ke saare 'New' maane jayenge)
    new_hacks = all_hacks # Direct copy because seen_ids is empty

    if new_hacks:
        if not BOT_TOKEN or not CHAT_ID:
            print("❌ Error: BOT_TOKEN or CHAT_ID not found in secrets.")
            return

        bot = Bot(token=BOT_TOKEN)
        print(f"🔥 Sending {len(new_hacks)} alerts to Telegram...")
        
        count = 0
        for hack in new_hacks:
            try:
                # Sirf top 15 bhejo taaki Telegram Block na kare (Spam protection)
                if count >= 15: 
                    print("✋ Stopping after 15 messages to prevent spam ban.")
                    break
                
                await bot.send_message(chat_id=CHAT_ID, text=hack['text'], parse_mode='Markdown')
                print(f"   Sent: {hack['text'].splitlines()[0]}")
                await asyncio.sleep(1.5) # Thoda slow bhejo
                count += 1
            except Exception as e:
                print(f"   ❌ Failed to send: {e}")
        
        # Ab hum file mein save kar denge taaki agli baar spam na ho
        # Pehle ke IDs load karo taaki wo lost na ho jayein (Optional)
        final_ids = [h['id'] for h in new_hacks]
        with open(DB_FILE, 'w') as f:
            json.dump(final_ids, f)
            print("✅ Database updated for next time.")

    else:
        print("😴 No hackathons found at all (Check crawlers).")

if __name__ == "__main__":
    asyncio.run(run_bot())