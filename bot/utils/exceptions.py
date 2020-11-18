from tortoise.exceptions import FieldError
from discord.errors import DiscordException


class DatabaseCheckError(FieldError):
    """Base exception for failing checks in models."""
    pass


class ValidationError(DatabaseCheckError):
    """When model is not constructed by rules we've decided."""
    pass


class ZeroLengthCharacterString(DatabaseCheckError):
    """When Char field is empty but it is not allowed to be empty."""
    pass


class NonNegativeValue(DatabaseCheckError):
    """When model field has non-allowed negative value."""
    pass


class FieldOutOfRange(DatabaseCheckError):
    """When field has to many/little chars (Char field) or number is too big/low (int field)."""
    pass


class DatabaseMissingData(DiscordException):
    pass
