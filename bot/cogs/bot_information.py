import os
import time
import psutil
import logging

import timeago
import discord
from discord.ext import commands, tasks

from bot import Licensy
from bot.utils.licence_helper import get_current_time
from bot.utils.message_handler import new_vote_message
from bot.utils.activities import ActivityCycle, DynamicActivity
from bot.utils.misc import construct_load_bar, embed_space
from bot.utils.embed_handler import info, success, construct_embed, suggestion


logger = logging.getLogger(__name__)


class BotInformation(commands.Cog):
    def __init__(self, bot: Licensy):
        self.bot = bot
        self.activities = ActivityCycle()
        self.add_activities()
        self.activity_loop.start()
        self.process = psutil.Process(os.getpid())

    def cog_unload(self):
        self.activity_loop.cancel()

    def add_activities(self) -> None:
        """Add activities to cycle."""
        self.activities.add(
            DynamicActivity(
                type=discord.ActivityType.watching,
                name_callable=lambda: "{} guilds".format(len(self.bot.guilds))
            )
        )
        self.activities.add(
            DynamicActivity(
                type=discord.ActivityType.watching,
                name_callable=lambda: "TODO get stored license count",
                name_suffix=" licenses"
            )
        )
        self.activities.add(
            DynamicActivity(
                type=discord.ActivityType.watching,
                name_callable=lambda: "TODO get licensed members count",
                name_suffix=" licenses"
            )
        )
        self.activities.add(discord.Game(name="roles!"))

    @tasks.loop(minutes=5)
    async def activity_loop(self):
        if not self.bot.update_in_progress:
            await self.bot.change_presence(activity=await self.activities.next())

    @activity_loop.before_loop
    async def before_activity_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Activity loop started!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        If bot is mentioned in message (both in guild and DM) then show prefix that is used there.

        Messages longer than 25 chars are not considered bot pings and we will skip those.
        """
        if self.bot.user in message.mentions and not message.author.bot and len(message.content) < 25:
            prefix = await self.bot.get_guild_prefix(message.guild)

            if message.guild is None:
                await message.channel.send(embed=info(f"My prefix here is **{prefix}**"))
            else:
                await message.channel.send(embed=info(f"My prefix in this guild is **{prefix}**", message.guild.me))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        guild_log_channel = self.bot.config.GUILD_LOG_CHANNEL_ID

        message = (
            f"Bot has been added to **{guild}**\n"
            f"New members **{len(guild.members)}**\n"
            f"There is **{len(self.bot.guilds)}** guilds now."
        )

        await guild_log_channel.send(embed=info(message, guild.me, "Guild join"))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_log_channel = self.bot.config.GUILD_LOG_CHANNEL_ID

        message = (
            f"Bot has been removed from **{guild}**\n"
            f"Lost members **{len(guild.members)}**\n"
            f"There is **{len(self.bot.guilds)}** guilds now."
        )

        await guild_log_channel.send(embed=info(message, None, "Guild remove"))

    @commands.command()
    async def ping(self, ctx):
        """
        Shows bot ping.

        Output
        -------
        Message with 2 numeric values, first value is REST API latency and second one is Discord gateway latency.
        """
        before = time.monotonic()
        message = await ctx.send(embed=info("Pong", ctx.me))
        ping = (time.monotonic() - before) * 1000

        results = (
            f":ping_pong:   |   {int(ping)}ms\n"
            f":timer:   |   {self.bot.latency * 1000:.0f}ms"
        )

        await message.edit(embed=info(results, ctx.me, title="Results:"))

    @commands.command()
    async def invite(self, ctx):
        """
        Shows bot invite link.

        Output
        -------
        Discord invite link that can be used to invite the bot to your guild.
        """
        description = f"Use this **[invite link]({self.get_bot_invite_link()})** to invite me."
        await ctx.send(embed=info(description, ctx.me, title="Invite me :)"))

    @commands.command(aliases=["support"])
    async def get_support(self, ctx):
        """
        Shows invite to the support server.

        Output
        -------
        Link to Discord support server.
        """
        description = (
            f"Join **[support server]({self.bot.config.SUPPORT_CHANNEL_INVITE})** "
            f"for questions, suggestions and support."
        )
        await ctx.send(embed=info(description, ctx.me, title="Ask away!"))

    @commands.command()
    async def donate(self, ctx):
        """
        Support development.

        Output
        -------
        Shows link for donations, link to bot listing voting and link to source code.
        """
        description = (
            f"Donate on Patreon: [patreon link]({self.bot.config.PATREON_LINK})\n"
            f"Donate on Paypal: [paypal link]({self.bot.config.PAYPAL_LINK})\n\n"
            "Additional things you can do to support:\n\n"
            f"Vote for the bot: [vote link]({self.bot.config.TOP_GG_VOTE_LINK})\n\n"
            f"Take a look at the source code: {self.bot.config.SOURCE_CODE_LINK}\n"
            "Any improvements/suggestions are welcome. If you find it helpful feel free to star the repo ;)"
        )
        await ctx.send(embed=info(description, ctx.me, title="Support the development:"))

    @commands.command()
    async def vote(self, ctx):
        """
        Vote for Licensy on top.gg (bot list).

        Output
        -------
        Link to top.gg bot listing.
        """
        await ctx.send(embed=info(self.bot.config.TOP_GG_VOTE_LINK, ctx.me, title="Thank you."))

    @commands.command(aliases=("git", "github"))
    async def source(self, ctx):
        """
        Shows link to Github source code.

        Output
        -------
        Link to source code on Github.
        """
        msg = (
            f"Any improvements/suggestions are welcome. If you find it helpful feel free to star the repo ;)\n\n"
            f"{self.bot.config.SOURCE_CODE_LINK}"
        )
        await ctx.send(embed=info(msg, ctx.me, title="Source code"))

    @commands.command(aliases=("status", "statistics", "about"))
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def stats(self, ctx):
        """
        Shows bot information (stats/links/etc).
        """
        bot_ram_usage = self.process.memory_full_info().rss / 1024 ** 2
        bot_ram_usage = f"{bot_ram_usage:.2f} MB"
        bot_ram_usage_bar = construct_load_bar(self.process.memory_percent(), bot_ram_usage)

        virtual_memory = psutil.virtual_memory()
        server_ram_usage = f"{virtual_memory.used/1024/1024:.0f} MB"
        server_ram_usage_bar = construct_load_bar(virtual_memory.percent, server_ram_usage)

        cpu_count = psutil.cpu_count()

        bot_cpu_usage = self.process.cpu_percent()
        bot_cpu_usage = bot_cpu_usage if bot_cpu_usage <= 100 else bot_cpu_usage / cpu_count
        bot_cpu_usage_bar = construct_load_bar(bot_cpu_usage)

        server_cpu_usage = psutil.cpu_percent()
        server_cpu_usage = server_cpu_usage if server_cpu_usage <=100 else server_cpu_usage / cpu_count
        server_cpu_usage_bar = construct_load_bar(server_cpu_usage)

        io_counters = self.process.io_counters()
        io_read_bytes = f"{io_counters.read_bytes/1024/1024:.3f}MB"
        io_write_bytes = f"{io_counters.write_bytes/1024/1024:.3f}MB"

        footer = (
            f"[Invite]({self.get_bot_invite_link()})"
            f" | [Donate]({self.bot.config.PATREON_LINK})"
            f" | [Support server]({self.bot.config.SUPPORT_CHANNEL_INVITE})"
            f" | [Vote]({self.bot.config.TOP_GG_VOTE_LINK})"
            f" | [Github]({self.bot.config.SOURCE_CODE_LINK})"
        )

        # The weird numbers is just guessing number of spaces so the lines align
        # Needed since embeds are not monospaced font
        field_content = (
            f"**Bot RAM usage:**{embed_space*7}{bot_ram_usage_bar}\n"
            f"**Server RAM usage:**{embed_space}{server_ram_usage_bar}\n"
            f"**Bot CPU usage:**{embed_space*9}{bot_cpu_usage_bar}\n"
            f"**Server CPU usage:**{embed_space*3}{server_cpu_usage_bar}\n"
            f"**IO (r/w):** {io_read_bytes} / {io_write_bytes}\n"
            f"\n**Links:\n**" + footer
        )

        fields = {
            "Last boot": self.last_boot(),
            "Developer": self.bot.owner_mention,
            "Library": f"discord.py {discord.__version__}",
            "Servers": len(self.bot.guilds),
            "Average users:": f"{round(len(self.bot.users) / len(self.bot.guilds))} users/server",
            "Total users": len(self.bot.users),
            "Commands": len(self.bot.commands),
            "Active licenses:": 0,
            "Stored licenses:": 0,
            "Server info": field_content,
        }

        embed = construct_embed(ctx.me, **fields)
        await ctx.send(embed=embed)

    @commands.command()
    async def uptime(self, ctx):
        """
        Shows time since last boot.

        Output
        -------
        Humanized string representing time since boot.
        """
        await ctx.send(embed=info(self.last_boot(), ctx.me, title="Booted:"))

    @commands.command()
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def suggest(self, ctx, *, message: str):
        """
        Suggest idea/improvement for the bot.

        This message will get sent directly to the developer channel.
        You can also join the support server and suggest there.
        """
        suggestion_channel = self.bot.get_channel(self.bot.config.SUGGESTIONS_CHANNEL_ID)

        suggestion_msg = await suggestion_channel.send(embed=suggestion(message, ctx.author, ctx=ctx))
        await new_vote_message(suggestion_msg)

        await ctx.send(embed=success("Suggestion has been sent, thank you.", ctx.me), delete_after=5)

    def last_boot(self) -> str:
        """
        Get last boot time in humanized form.

        Returns
        -------
        last boot time (str)
            Boot time in humanized form aka description instead of numerals (eg. 2 hours ago, 1 week ago etc)
        """
        return timeago.format(get_current_time() - self.bot.up_time_start_time)

    def get_bot_invite_link(self) -> str:
        """
        Constructs bot invite link.

        Returns
        -------
        bot invite url: str
            Link that can be used for inviting bot to Discord guilds.
        """
        return discord.utils.oauth_url(self.bot.user.id, permissions=self.bot.config.BOT_PERMISSIONS)


def setup(bot):
    bot.add_cog(BotInformation(bot))
