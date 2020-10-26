import logging
from typing import List

import discord
import discord_argparse
from discord.ext import commands, tasks

from bot import Licensy, models
from bot.utils.converters import RolePacket
from bot.utils.licence_helper import LicenseFormatter


logger = logging.getLogger(__name__)


async def default_guild_reminders(ctx) -> models.ReminderActivations:
    """This is a workaround because model.copy() does not seem to be working.
    Instead of copy method we'll just create new model with the same data and return it.

    Reminder as why it doesn't seem to work:
    self._custom_generated_pk is set in model init but we don't get it in get(), thus the clone()
    does not get it either but the save() needs it!?
    """
    guild_reminders = await models.ReminderActivations.get(guild__id=ctx.guild.id)
    copy = await models.ReminderActivations.create_easy(*guild_reminders.get_all_activations())
    return copy


class Licenses(commands.Cog):
    def __init__(self, bot: Licensy):
        self.bot = bot

    @tasks.loop(minutes=1.0)
    async def license_expiration_check(self):
        try:
            await self.check_all_active_licenses()
        except Exception as e:
            logger.critical(e)

    @license_expiration_check.before_loop
    async def before_license_expiration_check(self):
        logger.info("Starting license expiration check loop..")
        await self.bot.wait_until_ready()
        logger.info("License expiration check loop started!")

    async def check_all_active_licenses(self):
        pass  # TODO placeholder

    async def remove_role(self, member_id, guild_id, licensed_role_id):
        pass  # TODO placeholder

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Create guild table for new guild."""
        pass  # TODO placeholder

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Remove guild table (and removing all tied data to guild) from database."""
        pass  # TODO placeholder

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Remove role from database and all data tied to it."""
        pass  # TODO placeholder

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """
        If member gets his role (which has a active license currently) removed manually by member using Discord
        client then treat that as the licensed role has expired/was revoked.
        """
        pass  # TODO placeholder

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def revoke(self, ctx, member: discord.Member, role: discord.Role):
        """Revoke active subscription from member."""
        pass  # TODO placeholder

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def revoke_all(self, ctx, member: discord.Member):
        """Revoke ALL active subscriptions from member."""
        pass  # TODO placeholder

    @commands.command(aliases=["authorize", "activate"])
    async def redeem(self, ctx, license_key: str):
        pass  # TODO placeholder

    @commands.command(allieses=["add"])
    @commands.has_permissions(manage_roles=True)
    async def add_license(self, ctx, license_key: str, member: discord.Member):
        """Manually add license to member."""
        pass  # TODO placeholder

    async def activate_license(self, license_key: str, guild_id: int, role_id: int, member: discord.Member) -> bool:
        """Helper method."""
        pass  # TODO placeholder

    param_converter = discord_argparse.ArgumentConverter(
        role_packet=discord_argparse.RequiredArgument(
            RolePacket,
            doc="Role_packet to use."
        ),
        regenerating=discord_argparse.OptionalArgument(
            bool,
            doc="Is it regenerating?",
            default=False
        ),
        usages=discord_argparse.OptionalArgument(
            int,
            doc="How much usages.",
            default=1
        ),
        reminders=discord_argparse.OptionalArgument(
            List[int],
            doc="Reminders to use.",
            default=default_guild_reminders
        )
    )

    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.command()
    async def generate(self, ctx, *, params: param_converter = param_converter.defaults()):
        guild = await models.Guild.get(id=ctx.guild.id)
        key = LicenseFormatter.generate_single(guild.custom_license_format, guild.license_branding)
        data = {
            "key": key,
            "guild": guild,
            "reminder_activations": params.pop("reminders"),
            **params
        }
        await ctx.send(f"{data}")
        await models.License.create(**data)

    @commands.command(aliases=["licences"])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def licenses(self, ctx, license_role: discord.Role = None):
        pass  # TODO placeholder

    @commands.command(alliases=["random_licenses"])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def random_license(self, ctx, number: int = 10):
        pass  # TODO placeholder

    @commands.command(aliases=["data"])
    @commands.guild_only()
    async def member_data(self, ctx, member: discord.Member = None):
        pass  # TODO placeholder

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def delete_license(self, ctx, license_key: str):
        """Deletes specified stored license."""
        pass  # TODO placeholder

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def delete_all(self, ctx):
        """
        Deletes all stored guild licenses.

        You will have to reply with "yes" for confirmation.
        """
        pass  # TODO placeholder


def setup(bot):
    bot.add_cog(Licenses(bot))
