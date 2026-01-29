import asyncio
from telegram import Bot

# Yaha apni details dhyan se paste karein
MY_TOKEN = "8572970702:AAFaU3LsAFSgR_GJE3hcIQXN6SKg8dQYG9k"
MY_CHAT_ID = "5949658048" # Ye numbers hone chahiye, string nahi

async def test_message():
    print("Testing bot connection...")
    try:
        bot = Bot(token=MY_TOKEN)
        # Ek simple message bhej kar dekhte hain
        await bot.send_message(chat_id=MY_CHAT_ID, text="✅ Badhai ho! Bot sahi se connect ho gaya hai.")
        print("Success! Message sent to Telegram.")
    except Exception as e:
        print(f"❌ Error aaya hai: {e}")
        print("Tip: Check karein ki Token sahi hai aur aapne bot ko 'Start' kiya hai.")

if __name__ == "__main__":
    asyncio.run(test_message())