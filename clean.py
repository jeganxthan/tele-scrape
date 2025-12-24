import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration (matching app.py defaults)
API_ID = int(os.getenv("API_ID", 34616802))
API_HASH = os.getenv("API_HASH", "b19339ceab122576f62b3886e267f35d")
SESSION_NAME = "series_session"
TARGET_CHAT = "hosico_catsbot"  # Change this if you want to clear a different chat

async def clear_history():
    print(f"🚀 Starting Telegram client to clear history for: {TARGET_CHAT}")
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    try:
        # Get the entity to ensure it's valid
        entity = await client.get_entity(TARGET_CHAT)
        print(f"✅ Found chat: {getattr(entity, 'title', entity.username)}")
        
        print("🗑️  Deleting history...")
        # Delete history
        await client.delete_dialog(entity, revoke=True)
        print("✅ History cleared.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(clear_history())
