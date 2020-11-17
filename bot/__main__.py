import os
import asyncio
import logging
from sys import stdout

from dotenv import load_dotenv
from tortoise import Tortoise

from bot import Licensy
from bot.config import DATABASE_DSN
from bot.utils.file_handlers import NonBlockingFileHandler


load_dotenv()

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s [%(name)s/%(funcName)s]", "%d-%m-%Y %H:%M:%S")

console_logger = logging.getLogger("console")
console = logging.StreamHandler(stdout)
console.setFormatter(formatter)
console_logger.addHandler(console)

file_handler = NonBlockingFileHandler("bot/logs/log.txt", encoding="utf-8")
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

root_logger.addHandler(console)  # TODO temporal for development stage, remove so it doesn't spam console


"""
uvloop is a fast, drop-in replacement of the built-in asyncio event loop that makes asyncio 2-4x faster.
It's a optional dependency as it is not supported on Windows.
"""
try:
    # noinspection PyUnresolvedReferences
    import uvloop
    uvloop.install()
except ImportError:
    console_logger.info("uvloop not supported on this system.")
else:
    console_logger.info("uvloop successfully installed.")


async def database_init():
    await Tortoise.init(
        db_url=DATABASE_DSN,
        modules={'models': ["bot.models.models"]}
    )
    await Tortoise.generate_schemas()


loop = asyncio.get_event_loop()
loop.run_until_complete(database_init())
Licensy(loop=loop).run(os.getenv("BOT_TOKEN"))
