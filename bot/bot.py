import sys
import logging
import asyncio
import traceback
import importlib
from pathlib import Path
from typing import Union, Generator
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError

import discord
from discord.ext import commands

from bot import config
from bot.models import Guild
from bot.utils.embed_handler import failure, log
from bot.utils.licence_helper import get_current_time
from bot.utils.errors import DatabaseMissingData


logger = logging.getLogger(__name__)
console_logger = logging.getLogger("console")


class Licensy(commands.Bot):
    def __init__(self, loop: asyncio.AbstractEventLoop = None):
        self.config = config
        self.update_in_progress: bool = False
        self.up_time_start_time = get_current_time()
        self._prefix_cache = {}
        self._language_cache = {}
        self._owner = None
        self._was_ready_once = False
        self._connected = False

        super().__init__(
            max_messages=None,
            loop=loop,
            command_prefix=Licensy.prefix_callable,
            case_insensitive=True,
            description=self.config.DESCRIPTION,
            owner_ids=set(self.config.BOT_OWNERS.values())
        )

    @property
    def owner_mention(self) -> str:
        """Owner is loaded on first on_ready, however if bot is just booted up this will return just 'loading'"""
        return self._owner.mention if self._owner is not None else "loading"

    @staticmethod
    async def prefix_callable(bot: "Licensy", message: discord.Message) -> str:
        return await bot.get_guild_prefix(message.guild)

    async def get_guild_prefix(self, guild: Union[discord.Guild, None]) -> str:
        default_prefix = self.config.DEFAULT_PREFIX

        # In case of DMs just return default prefix
        if guild is None:
            return default_prefix

        if guild.id in self._prefix_cache:
            # If prefix is empty string then no custom prefix is set
            if cached_prefix := self._prefix_cache[guild.id]:
                return cached_prefix
            else:
                return default_prefix
        else:
            # I guild is not found it could mean it's new, so just fetch it's prefix.
            try:
                fetched_prefix = (await Guild.get(id=guild.id).values_list("custom_prefix", flat=True))[0]
            except Exception as err:
                # If fetching prefix from database errors just use the default prefix.
                logger.error(f"Can't get guild {guild} prefix. Error:{err}. Using '{default_prefix}' as prefix.")
                return default_prefix
            else:
                self._prefix_cache[guild.id] = fetched_prefix

                if fetched_prefix:
                    return fetched_prefix
                else:
                    return default_prefix

    def update_prefix_cache(self, guild_id: int, new_prefix: str):
        self._prefix_cache[guild_id] = new_prefix

    def reload_config(self):
        importlib.reload(config)
        self.description = config.DESCRIPTION
        logger.info("Config successfully reloaded.")

    async def _populate_prefix_cache(self) -> None:
        prefix_data = await Guild.all().values_list("id", "custom_prefix")
        self._prefix_cache = {item[0]: item[1] for item in prefix_data}
        logger.info("Guild prefix cache successfully reloaded.")

    async def _populate_language_cache(self) -> None:
        language_data = await Guild.all().values_list("id", "language")
        self._language_cache = {item[0]: item[1] for item in language_data}
        logger.info("Guild language cache successfully reloaded.")

    async def _load_owner(self) -> discord.User:
        app_info = await self.application_info()
        return app_info.owner

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, connected: bool):
        self._connected = connected

    async def on_connect(self):
        self.connected = True
        logger.info("Connection to Discord established")

    async def on_disconnect(self):
        self.connected = False
        logger.warning("Connection to Discord lost.")

    async def on_ready(self):
        if not self._was_ready_once:
            await self._first_on_ready()
            self._was_ready_once = True

        # On each reconnect repopulate the cache
        await self._populate_prefix_cache()
        await self._populate_language_cache()

    async def _first_on_ready(self):
        console_logger.info(
            f"Successfully logged in as {self.user.name} ID:{self.user.id} \t"
            f"d.py {discord.__version__} \t"
            "Further logging output will go to log file.."
        )

        await self._load_extensions()
        self._owner = await self._load_owner()
        await self._startup_guild_database_check()

    async def _load_extensions(self):
        allowed_extensions = ("help", "guild", "bot_information", "licenses")  # TODO temporal for development stage

        for extension_path in Path("bot/cogs").glob("*.py"):
            extension_name = extension_path.stem

            if extension_name not in allowed_extensions:
                continue

            dotted_path = f"bot.cogs.{extension_name}"

            try:
                self.load_extension(dotted_path)
            except Exception as e:
                traceback_msg = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
                console_logger.info(f"Failed to load cog {dotted_path} - traceback:{traceback_msg}")
            else:
                console_logger.info(f"\tloaded {dotted_path}")

    async def _startup_guild_database_check(self):
        """
        Finds and adds any guilds that bot is in but are missing in the database.
        This is mainly for rare cases of Discord API issues where weird things can happen.

        Note: Never delete guilds just because database data and loaded guilds cache mismatch.
        It's possible that Discord down-times can cause bot to not see some guilds.
        """
        logger.info("Starting database guild checkup..")
        db_guild_ids = await Guild.all().values_list("id", flat=True)

        for guild in self.guilds:
            if guild.id not in db_guild_ids:
                message = f"Guild {guild.id} {guild} found in cache but not registered in database!"
                logger.critical(message)
                await self.log_error(message)

                await Guild.create(id=guild.id)

                success_message = f"Missing guild {guild.id} {guild} successfully registered in database."
                logger.critical(success_message)
                await self.log_error(success_message)

        logger.info("Database guild checkup done!")

    async def on_command_error(self, context: commands.Context, exception: Exception):
        ctx = context

        # If command has local error handler, return
        if hasattr(ctx.command, "on_error"):
            return

        # Get the original exception if there is any (for example CommandInvokeError,  ConversionError..)
        error = getattr(exception, "original", exception)

        if isinstance(error, commands.MissingPermissions):
            # Note that this check is specifically for error raised by @commands.has_permissions

            # Bot owners can bypass guild permissions
            if not await self.owner_bypass(ctx):
                await ctx.send(embed=failure(f"{error}"))

        elif isinstance(error, commands.CommandOnCooldown):
            # Cool-downs are ignored for bot owners
            if not await self.owner_bypass(ctx):
                await ctx.send(embed=failure(f"{error}"), delete_after=5)

        elif isinstance(error, discord.errors.Forbidden):
            # Reference https://discord.com/developers/docs/topics/opcodes-and-status-codes
            if error.code == 50013:  # Missing Permissions
                msg = f"{error}.\nCheck role hierarchy - I can only manage roles below me."
            elif error.code == 50007:  # Cannot send messages to this user.
                msg = f"{error}.\nHint: Disabled DMs?"
            else:
                msg = f"{error}."

            try:
                await ctx.send(embed=failure(msg))
            except discord.errors.Forbidden:
                # If we get Forbidden again just ignore.
                return

        elif isinstance(error, DatabaseMissingData):
            await ctx.send(embed=failure(f"Database error: {error}"))
            await self.log_error(f"{error}", ctx=ctx)

        elif isinstance(error, AsyncioTimeoutError):
            await ctx.send(embed=failure("You took too long to reply."))

        elif isinstance(error, commands.CommandError):
            # Capture any other command error and notify context. This is so we don't
            # log traceback from custom or any other command errors and spam the log channel.
            # (custom means any errors derived from CommandError but not available in dpy library)
            await ctx.send(embed=failure(f"{error}"), delete_after=5)

        else:
            # If we got here it means we got an unexpected error / possible bug.
            await self._deal_with_unexpected_command_error(ctx, error)

    async def _deal_with_unexpected_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Deals with unexpected command error by getting the traceback and basic info on context and sending it to log.
        It will also notify the context channel about the error but in short note (will cut the message if it's too
        long as to not spam the chat).

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context where the error occurred.
        error: Exception
            Error that was raised.
        """
        error_type = type(error)

        # Don't spam the chat with long errors.
        feedback_error = str(error) if len(str(error)) < 200 else "Error too long to display."
        feedback_message = f"Uncaught {error_type} exception in command '{ctx.command}'"

        traceback_message = traceback.format_exception(etype=error_type, value=error, tb=error.__traceback__)
        log_message = f"{feedback_message} {traceback_message}"

        logger.critical(log_message)
        await self.log_error(log_message, ctx=ctx)
        await ctx.send(embed=failure(f"{feedback_message}: {feedback_error}"))

    async def on_error(self, event: str, *args, **kwargs):
        ctx = self._try_to_get_context(*args, **kwargs)
        exception_type, exception_value, exception_traceback = sys.exc_info()

        if isinstance(exception_type, discord.Forbidden):
            return  # Ignore annoying messages (eg. if user disables DMs and event tries to DM)

        traceback_message = traceback.format_exception(
            etype=exception_type,
            value=exception_value,
            tb=exception_traceback
        )

        log_message = f"{event} event error exception!\n{traceback_message}"
        logger.critical(log_message)
        await self.log_error(log_message, ctx=ctx)

    @classmethod
    def _try_to_get_context(cls, *args, **kwargs) -> Union[commands.Context, None]:
        """
        Made as a helper method for on_error event.
        Tries to extract context from *args and **kwargs, if not found returns None.

        Returns
        -------
        context: Union[commands.Context, None]
            Context if found else None. Context prefix might not be accurate.
        """
        if (ctx := kwargs.pop("ctx", None)) is not None:
            return ctx

        for arg in args:
            if isinstance(arg, commands.Context):
                return arg

        # Sometimes it isn't context but message and context can be recreated with it.
        for arg in args:
            if isinstance(arg, discord.Message):
                return commands.Context(message=arg, prefix="dummy")

    async def owner_bypass(self, ctx: commands.Context) -> bool:
        """
        Bot owners can bypass guild permissions and command cool-downs.
        Bot owners are set from config upon bot initialization.

        Parameters
        ----------
        ctx: discord.ext.commands.Context
            Context where the command was called.
            If the command message author is one of bot owners then re-invoke the command.
        Returns
        -------
        is_developer: bool
            Is context message author is one of bot owners or not.

        """
        if ctx.message.author.id not in self.owner_ids:
            return False

        # reinvoke() bypasses error handlers so we surround it with try/catch and just log the errors.
        try:
            await ctx.reinvoke()
        except Exception as e:
            logger.warning(f"Re-invoking command for owner bypass failed: {ctx.message} {e}")
            await ctx.send(embed=failure(f"{e}"))
        else:
            return True

    async def log_exception(self, exception: Exception, *, ctx: Union[commands.Context, None] = None):
        """Similar to log_error only that this takes exception as argument and extracts the traceback."""
        traceback_msg = "".join(traceback.format_tb(exception.__traceback__))
        await self.log_error(traceback_msg, ctx=ctx)

    async def log_error(self, message: str, *, ctx: Union[commands.Context, None] = None):
        """
        Logs error message to developer Discord channel (that is set in config).
        Method will not send message if client is disconnected or not ready and it can deal with sending multiple
        messages if message is over the character limit.

        Parameters
        ----------
        message: str
            Message to send to the channel.
        ctx: Union[commands.Context, None], default value is None
            If you have ctx pass it and the message sent will have more information in its footer,
            such as guild, author and channel info. Good so you know from where the error came from.
        """
        if not self.is_ready() or not self.connected:
            return

        error_log_channel = self.get_channel(self.config.LOG_CHANNEL_ID)
        if error_log_channel is None:
            logger.critical("Can't send to error log channel as error log channel can't be found!")
            return

        split_messages = list(Licensy.split_string_into_chunks(message, 1800))

        for count, message in enumerate(split_messages):
            if count > 5:
                await error_log_channel.send("```Stopping spam, too many pages. See log for more info.```")
                break

            title = f"Log {count + 1}/{len(split_messages)}"

            if count == 0:
                # Log with full info only on the first log message.
                log_embed = log(message, ctx=ctx, title=title)
            else:
                log_embed = log(message, title=title)

            await error_log_channel.send(embed=log_embed)

    @staticmethod
    def split_string_into_chunks(string: str, chunk_size: int) -> Generator[str, None, None]:
        """Simple generator that splits string into more smaller strings (chunks)."""
        for i in range(0, len(string), chunk_size):
            yield string[i:i + chunk_size]
