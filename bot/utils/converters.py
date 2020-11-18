import re

from discord.ext.commands import BadArgument, Context, Converter

from bot import models


class Duration(Converter):
    """
    Convert duration strings into integer representing minute duration.
    Original source: https://github.com/python-discord/bot/blob/master/bot/converters.py
    """

    duration_parser = re.compile(
        r"((?P<years>\d+?) ?(years|year|y) ?)?"
        r"((?P<months>\d+?) ?(months|month) ?)?"
        r"((?P<weeks>\d+?) ?(weeks|week|w) ?)?"
        r"((?P<days>\d+?) ?(days|day|d) ?)?"
        r"((?P<hours>\d+?) ?(hours|hour|h) ?)?"
        r"((?P<minutes>\d+?) ?(minutes|minute|min))?"
    )

    minute_converter = {
        "years": 365 * 24 * 60,
        "months": 30 * 24 * 60,
        "weeks": 7 * 24 * 60,
        "days": 24 * 60,
        "hours": 60,
        "minutes": 1
    }

    async def convert(self, ctx: Context, duration_string: str) -> int:
        """
        Convert duration strings into integer representing minute duration.
        Example "3m 7days" will be converted to 139680.

        Parameters
        ----------
        ctx: Context
            Command context.
        duration_string: str
            String that will be converted to duration. Some valid examples:
                5y 3months 7h
                3m 7weeks
                5hours 3years
                4w

            You can stack same keywords:
                3m 5m 7m
                1y 7d 1y

            Each entry has to be some number followed by one of the keywords defined in duration_parser.
            Converter is not case sensitive and support following keywords:
            - years: `years`, `year`, `y`
            - months: `months`, `month`
            - weeks: `weeks`, `week`, `w`
            - days: `days`, `day`, `d`
            - hours: `hours`, `hour`, `h`
            - minutes: 'minutes', `minute`, `min`

            Months do not have keyword 'm' because it can be confused for minutes.

        Returns
        -------
        minutes: int
            Total duration in minutes that was specified in duration_string.
        """
        minutes = 0

        for word in duration_string.split():
            match = self.duration_parser.fullmatch(word)
            if match is None or not match.group(0):
                raise BadArgument(f"Invalid duration provided `{word}`.")

            time_data = {unit: int(amount) for unit, amount in match.groupdict(default="0").items()}
            for unit, amount in time_data.items():
                minutes += self.minute_converter[unit] * amount

        return minutes


class NonNegativeInteger(Converter):
    async def convert(self, ctx: Context, argument: str) -> int:
        """
        Converts argument to non-negative integer (>=0).

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context for converter.
        argument: str
            Argument that we will try to convert to non-negative integer.

        Raises
        ------
        ValueError
            Argument can't be converted to int.

        discord.ext.commands.BadArgument
            If the argument is a negative integer.

        Returns
        -------
        non_negative_integer : int
            Integer that is not negative (>=0)
        """
        non_negative_integer = int(argument)
        if non_negative_integer < 0:
            raise BadArgument(f"Passed **{non_negative_integer}** integer cannot be negative.")
        else:
            return non_negative_integer


class PositiveInteger(int, Converter):
    async def convert(self, ctx: Context, argument: str) -> int:
        """
        Converts argument to positive integer (>0).

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context for converter.
        argument: str
            Argument that we will try to convert to positive integer.

        Raises
        ------
        ValueError
            Argument can't be converted to int.

        discord.ext.commands.BadArgument
            If the integer is not positive (<1).

        Returns
        -------
        positive_integer : int
            Integer that is positive (>0).
        """
        positive_integer = int(argument)
        if positive_integer < 1:
            raise BadArgument(f"Passed integer **{positive_integer}** must be larger than 0.")
        else:
            return positive_integer


class RolePacket(Converter):
    async def convert(self, ctx: Context, argument: str) -> models.RolePacket:
        """
        Converts argument to role packet.

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context for converter.
        argument: str
            Argument that we will try to convert to role packet.

        Raises
        ------
        discord.ext.commands.BadArgument
            If there is no role packet with such name.

        Returns
        -------
        role_packet : RolePacket
            Instance of role packet.
        """
        if not ctx.guild:
            raise BadArgument("Can't be used in DMs.")

        role_packet = await models.RolePacket.get_or_none(guild_id=ctx.guild.id, name=argument)
        if not role_packet:
            raise BadArgument("Role packet not found.")

        return role_packet


class ReminderActivations(Converter):
    async def convert(self, ctx: Context, activations) -> models.ReminderActivations:
        """
        Converts argument to role packet.

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context for converter.
        activations: List[int]
            Argument that we will try to convert to role packet.

        Raises
        ------
        discord.ext.commands.BadArgument
            If there is no role packet with such name.

        Returns
        -------
        reminder_activations : ReminderActivations
            Instance of reminder activations.
        """
        if len(activations) > 5:
            raise BadArgument("Maximum of 5 reminders possible.")

        try:
            return await models.ReminderActivations.create_easy(*activations)
        except Exception as e:
            raise BadArgument(e)
