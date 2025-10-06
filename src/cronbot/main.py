import asyncio
from .config import Settings
from .bot import create_bot

async def main():
    bot = await create_bot()
    token = Settings().DISCORD_TOKEN
    try:
        await bot.start(token)
    finally:
        bot._scheduler.stop()  # type: ignore[attr-defined]

if __name__ == "__main__":
    asyncio.run(main())
