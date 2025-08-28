import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import user_main, admin
from handlers import photo_print
from handlers import scan

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def main():
    dp.include_router(user_main.router)
    dp.include_router(photo_print.router)
    dp.include_router(admin.router)
    dp.include_router(scan.router)
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())