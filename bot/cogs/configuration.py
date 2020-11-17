import logging

import discord
from discord.ext import commands
from tortoise.exceptions import FieldError

from bot import Licensy, models
from bot.utils.i18n_handler import LANGUAGES
from bot.utils.licence_helper import LicenseFormatter
from bot.utils.embed_handler import success, failure, info


logger = logging.getLogger(__name__)


class Configuration(commands.Cog):
    def __init__(self, bot: Licensy):
        self.bot = bot

    @commands.command(aliases=["guild_data"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def show_configuration(self, ctx):
        """
        Show current guild configuration.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)
        await ctx.send(embed=info(f"{guild_data}"))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def prefix(self, ctx, *, prefix: str):
        """
        Changes guild prefix.

        Parameters
        ----------
        prefix: str
            New prefix to be used in guild. Maximum size is 10 characters.
        """
        if ctx.prefix == prefix:
            await ctx.send(embed=failure(f"Already using prefix **{prefix}**"))
        elif len(prefix) > models.Guild.MAX_PREFIX_LENGTH:
            await ctx.send(
                embed=failure(f"Prefix is too long! Maximum of {models.Guild.MAX_PREFIX_LENGTH} characters please.")
            )
        else:
            await models.Guild.get(id=ctx.guild.id).update(custom_prefix=prefix)
            self.bot.update_prefix_cache(ctx.guild.id, prefix)
            await ctx.send(embed=success(f"Successfully changed prefix to **{prefix}**"))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def license_format(self, ctx, license_format: str):
        if LicenseFormatter.is_secure(license_format):
            await models.Guild.get(id=ctx.guild.id).update(custom_license_format=license_format)
            await ctx.send(embed=success("Successfully changed license format."))
        else:
            await ctx.send(
                embed=failure(
                    "Format is not secure enough.\n\n"
                    f"Current permutation count: {LicenseFormatter.get_format_permutations(license_format)}\n"
                    f"Required permutation count: {LicenseFormatter.min_permutation_count}"
                )
            )

    @commands.command(aliases=["branding"])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def license_branding(self, ctx, license_branding: str):
        if len(license_branding) > models.Guild.MAX_BRANDING_LENGTH:
            await ctx.send(
                embed=failure(f"Branding is too long! Maximum of {models.Guild.MAX_BRANDING_LENGTH} characters please.")
            )
        else:
            await models.Guild.get(id=ctx.guild.id).update(license_branding=license_branding)
            await ctx.send(embed=success("Successfully updated guild branding."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def timezone(self, ctx, timezone: int):
        """
        Changes guild timezone.

        Parameters
        ----------
        timezone: int
            Timezone in UTC (from -12 to 14).

            Note that this does not change bot behaviour in any way, you cannot change the bot timezone itself.
            This is just used to displaying bot time in your guild timezone.
        """
        if timezone not in range(-12, 15):
            await ctx.send(embed=failure("Invalid UTC timezone."))
        else:
            await models.Guild.get(id=ctx.guild.id).update(timezone=timezone)
            await ctx.send(embed=success("Successfully updated guild timezone."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def dm_redeem(self, ctx, state: bool):
        """
        Enables or disables redemption of licenses (made in this guild) in bot DMs.

        Parameters
        ----------
        state: bool
            State to enable to, either:
            True, 1, T
            or
            False, 0, F
        """
        await models.Guild.get(id=ctx.guild.id).update(enable_dm_redeem=state)
        await ctx.send(embed=success(f"Successfully set license DM redeem to **{state}**."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def language(self, ctx, language: str):
        """
        Change language the bot will use in this guild.

        To see a list of all supported languages call this command with random string as language.

        Parameters
        ----------
        language: str
            Two letter language code as per ISO 639-1 standard.
        """
        language = language.lower()

        if language not in LANGUAGES:
            available = ", ".join(LANGUAGES)
            await ctx.send(embed=failure(f"**{language}** is not found in available languages: {available}"))
        else:
            await models.Guild.get(id=ctx.guild.id).update(language=language)
            await ctx.send(embed=success(f"Successfully set guild language to **{language}**."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def toggle_reminders(self, ctx):
        """
        Enable/disable bot sending ANY reminders.

        Toggle means it will disable if enabled and vice versa.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)

        if guild_data.reminders_enabled:
            new_state, msg_state = False, "turned off"
        else:
            new_state, msg_state = True, "turned on"

        guild_data.reminders_enabled = new_state
        await guild_data.save()
        await ctx.send(embed=success(f"Sending any bot reminders is successfully {msg_state}."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def edit_default_reminders(
        self,
        ctx,
        first_activation: int,
        second_activation: int = 0,
        third_activation: int = 0,
        fourth_activation: int = 0,
        fifth_activation: int = 0
    ):
        """
        Edit default guild reminders.

        When creating new role packet without specifying reminders then these defaults are used.
        All values are in minutes and there can be up to 5 reminders.
        Reminders have to be sorted from highest to smallest if multiple are passed.

        Example usage:
        !edit_default_reminders 300
        !edit_default_reminders 300 290 250 240 200

        :param first_activation: int
        :param second_activation: int
        :param third_activation: int
        :param fourth_activation: int
        :param fifth_activation: int
        Al of the above params: How many minutes before license expiration will his reminder be sent.
        """
        reminders = await models.ReminderActivations.get(guild__id=ctx.guild.id)
        reminders.first_activation = first_activation
        reminders.second_activation = second_activation
        reminders.third_activation = third_activation
        reminders.fourth_activation = fourth_activation
        reminders.fifth_activation = fifth_activation

        try:
            await reminders.save()
        except FieldError as e:
            await ctx.send(embed=failure(str(e)))
        else:
            await ctx.send(embed=success("Successfully edited default guild reminders."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_reminders_channel(self, ctx, reminders_channel: discord.TextChannel):
        """
        Set reminders channel where bot will send reminders.
        """
        if not reminders_channel.permissions_for(ctx.me).send_messages:
            return await ctx.send(embed=failure(f"I can't set reminders channel on as I don't have permissions to send messages to it {reminders_channel.mention}!"))

        await models.Guild.get(id=ctx.guild.id).update(reminders_channel_id=reminders_channel.id)
        success_embed = success(f"Successfully set reminders channel {reminders_channel.mention}.")
        await ctx.send(embed=success_embed)
        await reminders_channel.send(embed=success_embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def disable_reminders_channel(self, ctx):
        """
        Disable reminders channel where bot sends reminders.
        """
        await models.Guild.get(id=ctx.guild.id).update(reminders_channel_id=0)
        await ctx.send(embed=success(f"Successfully disabled reminders channel."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def toggle_reminders_channel_ping(self, ctx):
        """
        Enable/disable bot pinging members when sending message to reminder channel.

        Toggle means it will disable if enabled and vice versa.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)
        reminder_channel = self.bot.get_channel(guild_data.reminders_channel_id)

        if guild_data.reminders_ping_in_reminders_channel:
            new_state, msg_state = False, "turned off"
        else:
            new_state, msg_state = True, "turned on"
            if reminder_channel is None:
                return await ctx.send(embed=failure(f"I can't turn pings on as I can't find reminders channel {guild_data.reminders_channel_id}!"))
            elif not reminder_channel.permissions_for(ctx.me).send_messages:
                return await ctx.send(embed=failure(f"I can't turn pings on as I don't have permissions to send messages to reminders channel {reminder_channel.mention}!"))

        guild_data.reminders_ping_in_reminders_channel = new_state
        await guild_data.save()
        success_embed = success(f"Pinging members in reminder channel successfully {msg_state}.")
        await ctx.send(embed=success_embed)
        await reminder_channel.send(embed=success_embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def toggle_reminders_dm(self, ctx):
        """
        Enable/disable bot sending reminders to member DMs.

        Toggle means it will disable if enabled and vice versa.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)

        if guild_data.reminders_send_to_dm:
            new_state, msg_state = False, "turned off"
        else:
            new_state, msg_state = True, "turned on"

        guild_data.reminders_send_to_dm = new_state
        await guild_data.save()
        success_embed = success(f"Sending reminders to member DMs successfully {msg_state}.")
        await ctx.send(embed=success_embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup_license_logs(self, ctx, license_log_channel: discord.TextChannel):
        """
        Set license log channel where bot will send log messages.

        Parameters
        ----------
        license_log_channel: discord.TextChannel
            Channel to set as license log channel.
        """
        await models.Guild.get(id=ctx.guild.id).update(license_log_channel_id=license_log_channel.id)
        await ctx.send(embed=success(f"Bot license log channel successfully set to {license_log_channel}."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def toggle_license_logs(self, ctx):
        """
        Enable/disable bot sending messages to license log channel.

        Toggle means it will disable if enabled and vice versa.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)
        logs_channel = self.bot.get_channel(guild_data.license_log_channel_id)

        if guild_data.license_log_channel_enabled:
            new_state, msg_state = False, "turned off"
        else:
            new_state, msg_state = True, "turned on"
            if logs_channel is None:
                return await ctx.send(embed=failure(f"I can't turn logs on as I can't find logs channel {guild_data.license_log_channel_id}!"))
            elif not logs_channel.permissions_for(ctx.me).send_messages:
                return await ctx.send(embed=failure(f"I can't turn logs on as I don't have permissions to send messages to logs channel {logs_channel.mention}!"))

        guild_data.license_log_channel_enabled = new_state
        await guild_data.save()
        success_embed = success(f"Bot license log channel successfully {msg_state}.")
        await ctx.send(embed=success_embed)
        await logs_channel.send(embed=success_embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup_diagnostics(self, ctx, diagnostics_channel: discord.TextChannel):
        """
        Set diagnostic channel where bot will send diagnostic messages.

        Parameters
        ----------
        diagnostics_channel: discord.TextChannel
            Channel to set as diagnostic channel.
        """
        await models.Guild.get(id=ctx.guild.id).update(diagnostics_channel_id=diagnostics_channel.id)
        await ctx.send(embed=success(f"Bot diagnostic channel successfully set to {diagnostics_channel}."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def toggle_diagnostics(self, ctx):
        """
        Enable/disable bot sending diagnostic messages to diagnostic channel.

        Toggle means it will disable if enabled and vice versa.
        """
        guild_data = await models.Guild.get(id=ctx.guild.id)
        diagnostic_channel = self.bot.get_channel(guild_data.diagnostic_channel_id)

        if guild_data.diagnostic_channel_enabled:
            new_state, msg_state = False, "turned off"
        else:
            new_state, msg_state = True, "turned on"
            if diagnostic_channel is None:
                return await ctx.send(embed=failure(f"I can't turn diagnostics on as I can't find diagnostics channel {guild_data.diagnostic_channel_id}!"))
            elif not diagnostic_channel.permissions_for(ctx.me).send_messages:
                return await ctx.send(embed=failure(f"I can't turn diagnostics on as I don't have permissions to send messages to diagnostics channel {diagnostic_channel.mention}!"))

        guild_data.diagnostic_channel_enabled = new_state
        await guild_data.save()
        success_embed = success(f"Bot diagnostics channel successfully {msg_state}.")
        await ctx.send(embed=success_embed)
        await diagnostic_channel.send(embed=success_embed)


def setup(bot):
    bot.add_cog(Configuration(bot))
