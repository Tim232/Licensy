import os
import logging

import dbl
from discord.ext import commands, tasks

from bot import Licensy


logger = logging.getLogger(__name__)


class TopGGApi(commands.Cog):
    """Handles interactions with the top.gg API.

    This cog is only so the bot can post number of guilds it's in to top.gg bot listing.
    """

    def __init__(self, bot: Licensy):
        self.bot = bot
        self.dbl_client = dbl.DBLClient(self.bot, os.getenv("TOP_GG_API_TOKEN"))
        self.update_stats_loop.start()

    def cog_unload(self):
        self.update_stats_loop.cancel()

    @tasks.loop(hours=12.0)
    async def update_stats_loop(self):
        """This function runs every 12 hours to automatically update server count on top.gg"""
        try:
            await self.dbl_client.post_guild_count()
        except dbl.DBLException as e:
            logger.exception(f"Failed to post server count: {e}")

    @update_stats_loop.before_loop
    async def before_update_stats_loop(self):
        await self.bot.wait_until_ready()

        try:
            await self.dbl_client.get_guild_count()
        except dbl.Unauthorized:
            logger.warning("top.gg invalid token passed, unloading cog.")
            self.update_stats_loop.cancel()
            self.bot.remove_cog(type(self).__name__)
        else:
            logger.info("top.gg update loop started!")


def setup(bot):
    bot.add_cog(TopGGApi(bot))
