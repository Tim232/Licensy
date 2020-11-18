import logging

import discord
from discord.ext import commands
from tortoise.exceptions import IntegrityError

from bot import Licensy, models
from bot.utils.misc import embed_space
from bot.utils.converters import PositiveInteger
from bot.utils.embed_handler import success, failure, info


logger = logging.getLogger(__name__)


class Roles(commands.Cog):
    def __init__(self, bot: Licensy):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def show_role_packets(self, ctx):
        """
        Shows all saved role packets from this guild.
        """
        packets = await models.RolePacket.filter(guild__id=ctx.guild.id)
        if not packets:
            return await ctx.send(embed=failure("Could not find any role packet for this guild."))

        packet_names = "\n".join(packet.name for packet in packets)
        await ctx.send(embed=info(packet_names, ctx.me, "Role packets"))

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def show_packet_data(self, ctx, packet_name: str):
        """
        Shows all roles for specific role packet.

        Arguments
        ----------
        packet_name: str
            Name of the role packet that you wish to show.
        """
        packet_roles = await models.PacketRole.filter(role_packet__name=packet_name).prefetch_related("role")
        if not packet_roles:
            return await ctx.send(embed=failure("Could not find any roles in this role packet."))

        message = (
            f"{ctx.guild.get_role(packet_role.role.id).mention} {packet_role.role.id} {packet_role.duration}m"
            for packet_role in packet_roles
        )
        await ctx.send(embed=info("\n".join(message), ctx.me, "Role packets"))

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def show_tier_hierarchy(self, ctx):
        """
        Shows hierarchy for tiered roles.

        Tiered role is a role that has tier level > 0
        """
        roles = await models.Role.filter(tier_level__gte=0)
        if not roles:
            return await ctx.send(embed=failure("Tier hierarchy not set. Not a single role has tier level > 0"))
        
        hierarchy = sorted(roles, key=lambda _role: (_role.tier_power, _role.tier_level))
        levels = {}
        for role in hierarchy:
            levels.setdefault(role.tier_power, [])
            levels[role.tier_power].append((role.id, role.tier_level))

        message = []
        for level, sub_tuple in levels.items():
            message.append(f"**Level {level}:**")
            for role_id, role_power in sub_tuple:
                message.append(f"{self.tab}{role_power} {self.safe_role_as_mention(ctx.guild, role_id)}")
            message.append("\n")

        await ctx.send(embed=info("\n".join(message), ctx.me, "Role hierarchy"))

    @classmethod
    def safe_role_as_mention(cls, guild: discord.Guild, role_id: int) -> str:
        role = guild.get_role(role_id)
        if role is None:
            return f"{role_id}"
        else:
            return role.mention

    @property
    def tab(self):
        return embed_space*4

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def edit_role(
        self,
        ctx,
        role: discord.Role,
        tier_level: PositiveInteger = 0,
        tier_power: PositiveInteger = 1
    ):
        role = await models.Role.get_or_create_easy(ctx.guild.id, role.id)
        role.tier_level = tier_level
        role.tier_power = tier_power
        try:
            await role.save()
        except IntegrityError:
            await ctx.send(embed=failure("Cannot have 2 roles with the same tier power and level."))
        else:
            await ctx.send(embed=success("Role updated."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def create_role_packet(
            self,
            ctx,
            name: str,
            default_role_duration_minutes: PositiveInteger
    ):
        """
        Arguments
        ----------
        name: str
            Name for accessing this role packet.
            Warning: No spaces allowed!
            Maximum of 50 characters.

        default_role_duration_minutes: PositiveInteger
            When roles are added to this packet this is their default duration unless otherwise specified
            (you can also specify it manually when adding new role).
        """
        guild = await models.Guild.get(id=ctx.guild.id)

        try:
            await models.RolePacket.create(
                guild=guild,
                name=name,
                default_role_duration=default_role_duration_minutes
            )
        except IntegrityError:
            # This also propagates driver exception, should be fixed in tortoise update
            # (it is properly caught but still shows up in log as traceback)
            await ctx.send(embed=failure("Role packet with that name already exists."))
        else:
            await ctx.send(embed=success("Role packet successfully created."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def add_packet_role(
            self,
            ctx,
            role_packet_name: str,
            role: discord.Role,
            duration_minutes: PositiveInteger = None
    ):
        """
        Add role to role packet.

        Arguments
        ----------
        role_packet_name: str
            Name of role packet to add to.

        role: discord.Role
            Role to add to role packet.

        duration_minutes: Optional[PositiveInteger]
            When role packet is redeemed how long will this role last in minutes.
            If not passed the it wil use default_role_duration_minutes value from it's role packet.
        """
        guild = await models.Guild.get(id=ctx.guild.id)
        db_role = await models.Role.get_or_create_easy(ctx.guild.id, role.id)
        role_packet = await models.RolePacket.get(name=role_packet_name, guild=guild)

        if duration_minutes is None:
            duration_minutes = role_packet.default_role_duration

        try:
            await models.PacketRole.create(role_packet=role_packet, duration=duration_minutes, role=db_role)
        except IntegrityError:
            await ctx.send(embed=failure("That role already exists in that role packet."))
        else:
            await ctx.send(embed=success("Packet role successfully added", ctx.me))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def remove_packet_role(
            self,
            ctx,
            role_packet_name: str,
            role: discord.Role
    ):
        """
        Removes role from role packet.

        Arguments
        ----------
        role_packet_name: str
            Name of role packet to add to.

        role: discord.Role
            Role to remove from role packet.
        """
        guild = await models.Guild.get(id=ctx.guild.id)
        db_role = await models.Role.get_or_create_easy(ctx.guild.id, role.id)
        role_packet = await models.RolePacket.get(guild=guild, name=role_packet_name)

        await models.PacketRole.get(role_packet=role_packet, role=db_role).delete()
        await ctx.send(embed=success("Packet role successfully removed.", ctx.me))

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def edit_packet_role(
            self,
            ctx,
            role_packet_name: str,
            role: discord.Role,
            duration_minutes: PositiveInteger
    ):
        """
        Change duration for role in role packet.

        Arguments
        ----------
        role_packet_name: str
            Name of role packet to add to.

        role: discord.Role
            Role from role packet to change duration for.

        duration_minutes: PositiveInteger
            New duration in minutes for the role.
        """
        guild = await models.Guild.get(id=ctx.guild.id)
        db_role = await models.Role.get_or_create_easy(ctx.guild.id, role.id)
        role_packet = await models.RolePacket.get(guild=guild, name=role_packet_name)
        await models.PacketRole.get(role_packet=role_packet, role=db_role).update(duration=duration_minutes)
        await ctx.send(embed=success("Packet role successfully updated.", ctx.me))


def setup(bot):
    bot.add_cog(Roles(bot))
