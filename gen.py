from telethon.sync import TelegramClient
import os
from dotenv import load_dotenv

load_dotenv("config.env")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

client = TelegramClient("telegramv3.session", API_ID, API_HASH)
client.start()  # ← Isso vai pedir número, código e criar o arquivo .session

print("Sessão salva com sucesso.")
