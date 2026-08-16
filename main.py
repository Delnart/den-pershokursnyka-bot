import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.db.db_setup import init_db

import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

from app.routers.controller_router import router as controller_router


async def init_db_with_retry(retries: int = 5, delay: float = 3.0):
    """
    Neon може мати cold start ~1–2 сек після авто-призупинення.
    Пробуємо підключитись кілька разів перед тим як впасти.
    """
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            print(f"✅ БД ініціалізована (спроба {attempt})")
            return
        except Exception as e:
            print(f"⚠️ Спроба {attempt}/{retries} — помилка БД: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise


async def main():
    bot = Bot(
       token=BOT_TOKEN,
       default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(controller_router)

    print("Ініціалізація БД...")
    await init_db_with_retry()

    print("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
   logging.basicConfig(level=logging.INFO, stream=sys.stdout)

   try:
       asyncio.run(main())
   except KeyboardInterrupt:
       print("Bot stopped")

