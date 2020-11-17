import logging
import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from bot import Licensy
from bot.models import models
from bot.utils.misc import tail
from bot.utils.paginator import Paginator
from bot.utils.converters import PositiveInteger
from bot.utils.embed_handler import success, failure


logger = logging.getLogger(__name__)


class BotOwnerCommands(commands.Cog):
    def __init__(self, bot: Licensy):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, extension_name: str):
        """
        Loads an extension.

        Parameters
        ----------
        ctx
        extension_name : str
            Cog name without suffix.

        """
        self.bot.load_extension(f"bot.cogs.{extension_name}")
        message = f"{extension_name} loaded."
        logger.info(message)
        await ctx.send(embed=success(message, ctx.me))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, extension_name: str):
        """
        Unloads an extension.

        Parameters
        ----------
        ctx
        extension_name : str
            Cog name without suffix.
        """
        if extension_name == Path(__file__).stem:
            return await ctx.send(embed=failure("This cog is protected, cannot unload."))

        self.bot.unload_extension(f"bot.cogs.{extension_name}")
        message = f"{extension_name} unloaded."
        logger.info(message)
        await ctx.send(embed=success(message, ctx.me))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def disconnect(self, ctx):
        """
        Should commit&close any database connections and then logout.
        Used for gracefully shutting it down in need of update.
        TODO: Placeholder code
        """
        pass

    @commands.command(hidden=True)
    @commands.is_owner()
    async def update(self, ctx, count_minutes: int = 15):
        if self.bot.update_in_progress:
            return await ctx.send(embed=failure("Update is already in progress!"))

        self.bot.update_in_progress = True

        for minutes in range(count_minutes, 0, -1):
            await self.bot.change_presence(activity=discord.Game(name=f"Update in {minutes}"))
            await asyncio.sleep(60)

        progress_msg = (
            "```diff                  \n"
            "- ---------------------- \n"
            "+   Update in progress   \n"
            "- ---------------------- \n"
            "```                        "
        )

        update_channel = self.bot.get_channel(self.bot.config.UPDATE_CHANNEL_ID)
        await update_channel.send(progress_msg)
        await self.bot.change_presence(activity=discord.Game(name="Update in progress!"))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def update_done(self, _ctx):
        msg = (
            "```diff                                                        \n"
            "- -------------------------------------------------------------\n"
            "+   Update done. All changes above this message are now live!  \n"
            "- -------------------------------------------------------------\n"
            "```                                                              "
        )

        update_channel = self.bot.get_channel(self.bot.config.UPDATE_CHANNEL_ID)
        await update_channel.send(msg)
        await self.bot.change_presence(activity=discord.Game(name="Update done."))
        self.bot.update_in_progress = False

    @commands.command(hidden=True)
    @commands.is_owner()
    async def show_log(self, ctx, lines: PositiveInteger = 100):
        """
        Shows last n lines from log text.
        Sends multiple messages at once if needed.

        Parameters
        ----------
        lines: PositiveInteger
            Number of last lines to show (default is 100, maximum is 10_000)
        """
        if lines > 10_000:
            lines = 10_000

        log = "".join(tail(lines))

        await Paginator.paginate(
            self.bot,
            ctx.author,
            ctx.author,
            log,
            title=f"Last {lines} log lines.\n\n",
            prefix="```DNS\n"
        )

    @commands.command(hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def valid(self, ctx, license_key: str):
        """
        Checks if passed license is valid.
        TODO: Placeholder code
        """
        pass

    @commands.command(hidden=True)
    @commands.is_owner()
    async def guilds_diagnostic(self, ctx):
        """
        Shows difference between database guilds and cache guilds.
        """
        loaded_guilds = tuple(guild.id for guild in self.bot.guilds)
        db_guilds = await models.Guild.all().values_list("id", flat=True)
        difference = set(loaded_guilds).symmetric_difference(set(db_guilds))
        message = (
            f"Loaded guilds: {len(loaded_guilds)}\n"
            f"Database guilds: {len(db_guilds)}\n"
            f"Difference: {difference}"
        )
        await ctx.send(embed=success(message, ctx.me))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def guild_diagnostic(self, ctx, guild_id: int = None):
        """
        A shortened version of guild_info command without any checks and
        including additional data from the guild object.

        TODO: Placeholder code
        """
        if guild_id is None:
            if ctx.guild is None:
                return await ctx.send(embed=failure("No guild to use."))
            guild_id = ctx.guild.id

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            loaded_msg = "Guild ID not found in loaded guilds."
        else:
            loaded_msg = (
                f"Guild info:\n"
                f"Name: **{guild.name}**\n"
                f"Description: **{guild.description}**\n"
                f"Owner ID: **{guild.owner_id}**\n"
                f"Member count: **{guild.member_count}**\n"
                f"Role count: **{len(guild.roles)}**\n"
                f"Verification level: **{guild.verification_level}**\n"
                f"Premium tier: **{guild.premium_tier}**\n"
                f"System channel: **{guild.system_channel.id}**\n"
                f"Region: **{guild.region}**\n"
                f"Unavailable: **{guild.unavailable}**\n"
                f"Created date: **{guild.created_at}**\n"
                f"Features: **{guild.features}**"
            )

        guild_data = await models.Guild.get(id=guild_id)
        stored_license_count = 0
        active_license_count = 0

        db_msg = (
            f"Database guild info:\n"
            f"Stored licenses: **{stored_license_count}**\n"
            f"Active role subscriptions: **{active_license_count}**\n"
            f"Configuration: {guild_data}"
        )

        await ctx.send(embed=success(f"{db_msg}\n\n{loaded_msg}", ctx.me))


def setup(bot):
    bot.add_cog(BotOwnerCommands(bot))
