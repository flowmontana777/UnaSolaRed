import os
import asyncio
import logging

from telethon import TelegramClient
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

# Configuración de Una Red
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# Grupo de la radio
CHAT_ID = os.environ.get("RADIO_CHAT_ID")

# Cliente de Telegram
client = TelegramClient(
    "unared_radio",
    API_ID,
    API_HASH
)

async def start_radio():
    await client.start()
    print("Una Red Radio está conectada 📻")

async def main():
    await start_radio()

if __name__ == "__main__":
    asyncio.run(main())
