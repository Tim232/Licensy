from typing import Tuple

from tortoise.models import Model
from tortoise.query_utils import Q
from tortoise.queryset import QuerySet
from tortoise.exceptions import FieldError, IntegrityError, DoesNotExist
from tortoise.fields import (
    OneToOneField, ForeignKeyRelation, ForeignKeyField, SmallIntField, IntField,
    BigIntField, CharField, BooleanField, DatetimeField, CASCADE, RESTRICT
)

from bot.utils import i18n_handler
from bot.utils.licence_helper import LicenseFormatter


# TODO periodic check for cleaning data, example if LicensedMember has no more LicensedRoles then remove
# TODO DURATION?


class ReminderActivations(Model):
    """
    Reminders are when we send DM/ping to member whose license will soon expire.
    Values here represent MINUTES before license expiration.
    """
    first_activation = BigIntField(
        default=720,
        description=(
            "All values are in minutes representing how many minutes "
            "before license expiration will the reminder be sent."
        )
    )
    second_activation = BigIntField(default=0)
    third_activation = BigIntField(default=0)
    fourth_activation = BigIntField(default=0)
    fifth_activation = BigIntField(default=0)

    @classmethod
    async def create_easy(
        cls,
        first_activation: int,
        second_activation: int = 0,
        third_activation: int = 0,
        fourth_activation: int = 0,
        fifth_activation: int = 0
    ) -> "ReminderActivations":
        return await cls.create(
            first_activation=first_activation,
            second_activation=second_activation,
            third_activation=third_activation,
            fourth_activation=fourth_activation,
            fifth_activation=fifth_activation
        )

    def get_all_activations(self) -> Tuple[int, ...]:
        """Helper method for easier accessing all fields.

        If one of model activation fields change this also needs to change.
        """
        return (
            self.first_activation, self.second_activation, self.third_activation,
            self.fourth_activation, self.fifth_activation
        )

    def __getitem__(self, activation: int):
        return self.get_all_activations()[activation]

    async def _post_save(self, *args, **kwargs) -> None:
        self._check_valid_first_activation()
        self._check_activation_ranges()
        self._check_valid_order_activations()  # TODO does it get saved if this raises?

        await super()._post_save(*args, **kwargs)

    def _check_valid_first_activation(self):
        """This table, if it exists, should have at least one proper activation."""
        if not self[0] > 0:
            raise FieldError("Reminder first activation has to be enabled.")

    def _check_activation_ranges(self):
        """Activation value cannot be negative."""
        for activation in self.get_all_activations():
            if activation < 0:
                raise FieldError(f"Reminder activation value {activation} cannot be negative.")

    def _check_valid_order_activations(self):
        """Checks if activations are in good order.

        First activation has to be the highest number as it is first activation therefore it has to activate first
        so to achieve that it has to be the highest number as the number represent how long before license expiration
        will reminder activate.

        Every next activation has to be smaller than the previous (smaller == later reminder).
        Note that this also implies that there can be no duplicates.
        """
        activations = self.get_all_activations()
        for activation_pair in zip(activations, activations[1:]):
            if activation_pair[0] < activation_pair[1]:
                raise FieldError(
                    "Reminder activation fields have to be ordered from highest to lowest without duplicate values."
                )

    class Meta:
        table = "reminders_settings"


class Guild(Model):
    MAX_PREFIX_LENGTH = 10
    MAX_BRANDING_LENGTH = 50

    """Represents Discord guild(server)."""
    id = BigIntField(pk=True, generated=False, description="Guild ID.")
    custom_prefix = CharField(
        max_length=MAX_PREFIX_LENGTH,
        default="",
        description=(
            "Represents guild prefix used for calling commands."
            "If it's not set (empty string) then default bot prefix from config will be used."
        )
    )
    custom_license_format = CharField(
        max_length=100,
        default="",
        description="Format to use when generating license. If it's a empty string then default format is used."
    )
    license_branding = CharField(
        max_length=MAX_BRANDING_LENGTH,
        default="",
        description=(
            "Custom branding string to be displayed in generated license."
            "It's position can be changed by changing license format. Can be empty string."
        )
    )
    timezone = SmallIntField(
        default=0,
        description=(
            "Timezone integer offset from UTC+0 (which is default bot timezone)."
            "For internal calculations the default bot timezone is always used,"
            "this is only used for **displaying** expiration date for guild."
        )
    )
    enable_dm_redeem = BooleanField(default=True, description="Can the redeem command also be used in bot DMs?")
    preserve_previous_duration_duplicate = BooleanField(
        default=True,
        description=(
            "Behaviour to happen if the member redeems a role that he already has licenses for."
            "true - new duration will be sum of new duration + time remaining from the previous duration."
            "false - duration is reset and set to new duration only."
        )
    )
    preserve_previous_duration_tier_upgrade = BooleanField(
        default=True,
        description=(
            "Behaviour to happen if the member redeems a role that has the same tier power but a higher level "
            "as one of his existing licensed roles (if tier_level for both is >0 aka activated)."
            "true - new duration will be sum of new duration + time remaining from the previous duration."
            "false - duration is reset and set to new duration only."
        )
    )
    preserve_previous_duration_tier_miss = BooleanField(
        default=True,
        description=(
            "Behaviour to happen if the member redeems a role that has the same tier power but a lower level "
            "as one of his existing licensed roles (if tier_level for both is >0 aka activated)."
            "true - increase current duration with new duration"
            "false - nothing happens."
        )
    )
    nuke_data_on_member_leave = BooleanField(
        default=True,
        description=(
            "If bot gets event that member has left certain guild then all of that member data from that guild"
            "(active subscriptions etc) are immediately deleted. If False then nothing happens, data will get "
            "removed as usual - when time expires."
        )
    )
    language = CharField(max_length=2, default="en", description="Two letter language code as per ISO 639-1 standard.")
    reminders_enabled = BooleanField(
        default=True,
        description=(
            "Whether reminders are enabled or not. Reminders notify members before the license expires."
        )
    )
    reminder_activations = OneToOneField(
        "models.ReminderActivations",
        on_delete=RESTRICT,
        description="Will be created upon guild creation automatically. Stores default guild reminders.",
        related_name="guild"
    )
    reminders_channel_id = BigIntField(
        default=0,
        description=(
            "Guild channel ID where reminder message will be sent."
            "Value of 0 (or any invalid ID) will disable sending messages."
        )
    )
    reminders_ping_in_reminders_channel = BooleanField(
        default=False,
        description="Whether to ping the reminding member when sending to reminders channel."
    )
    reminders_send_to_dm = BooleanField(
        default=True,
        description=(
            "Whether to **also** send reminder to member DM."
            "Note: This does not affect message sending to reminder channel."
        )
    )
    license_log_channel_enabled = BooleanField(
        default=False,
        description=(
            "Whether to enable or disable license log channel."
        )
    )
    license_log_channel_id = BigIntField(
        default=0,
        description=(
            "Guild channel where license logging messages will be sent."
            "Example: redeem/add_licenses commands uses, when license activates/expires/regenerates."
            "Value of 0 (or any invalid ID) will disable sending messages."
            )
        )
    diagnostic_channel_enabled = BooleanField(
        default=False,
        description=(
            "Whether to enable or disable bot diagnostics channel."
        )
    )
    diagnostic_channel_id = BigIntField(
        default=0,
        description=(
            "Guild channel where bot diagnostic messages will be sent."
            "Examples: bot updates and their state (start/end),"
            "errors that came from usage of the bot in that guild, changing any guild settings."
            "Updates about on_guild_role_delete&on_member_role_remove."
            "Usage of revoke/revoke_all/generate/delete/delete all."
        )
    )

    class Meta:
        table = "guilds"

    def __str__(self):
        messages = [
            f"Guild ID: {self.id}",
            f"Custom prefix: {self.custom_prefix if self.custom_prefix else 'not set'}",
            f"Custom license format: {self.custom_license_format if self.custom_license_format else 'not set'}",
            f"License branding: {self.license_branding if self.license_branding else 'not set'}",
            f"Timezone: {self.timezone if self.timezone else 'not set, default'}",
            f"License DM redemption: {self.enable_dm_redeem}",
            f"preserve_previous_duration_duplicate: {self.preserve_previous_duration_duplicate}",
            f"preserve_previous_duration_tier_upgrade: {self.preserve_previous_duration_tier_upgrade}",
            f"preserve_previous_duration_tier_miss: {self.preserve_previous_duration_tier_miss}",
            f"nuke_data_on_member_leave: {self.nuke_data_on_member_leave}",
            f"Language: {self.language}",
            f"Reminders enabled: {self.reminders_enabled}"
        ]

        if self.reminders_enabled:
            reminders_channel = "Not set" if self.reminders_channel_id == 0 else f"{self.reminders_channel_id} <#{self.reminders_channel_id}>"
            messages.extend([
                f"Reminders channel: {reminders_channel}",
                f"Ping members in reminders channel: {self.reminders_ping_in_reminders_channel}",
                f"Send reminders to DMs: {self.reminders_send_to_dm}"
            ])

        messages.append(f"License log channel enabled: {self.license_log_channel_enabled}")
        if self.license_log_channel_enabled:
            messages.append(f"License log channel: {self.license_log_channel_id} <#{self.license_log_channel_id}>\n")

        messages.append(f"Diagnostics channel enabled: {self.diagnostic_channel_enabled}\n")
        if self.diagnostic_channel_enabled:
            messages.append(f"Diagnostic channel: {self.diagnostic_channel_id} <#{self.diagnostic_channel_id}>\n")

        return "\n".join(messages)

    async def _post_delete(self, *args, **kwargs) -> None:
        """Deals with deleting ReminderActivations table after this table is deleted."""
        await super()._post_delete(*args, **kwargs)
        await self.reminder_activations.delete()

    async def _pre_save(self, *args, **kwargs) -> None:
        custom_prefix_maximum_length = self._meta.fields_map['custom_prefix'].max_length
        custom_license_format_maximum_length = self._meta.fields_map['custom_license_format'].max_length
        license_branding_maximum_length = self._meta.fields_map['license_branding'].max_length
        language_maximum_length = self._meta.fields_map['language'].max_length

        if len(self.custom_prefix) > custom_prefix_maximum_length:
            raise FieldError(f"Custom prefix has to be under {custom_prefix_maximum_length} characters.")
        elif len(self.custom_license_format) > custom_license_format_maximum_length:
            raise FieldError(f"Custom format has to be under {custom_license_format_maximum_length} characters.")
        elif self.custom_license_format and not LicenseFormatter.is_secure(self.custom_license_format):
            generated_permutations = LicenseFormatter.get_format_permutations(self.custom_license_format)
            raise FieldError(
                f"Your custom license format '{self.custom_license_format}' is not secure enough!"
                f"Not enough possible permutations!"
                f"Required: {LicenseFormatter.min_permutation_count}, got: {generated_permutations}"
            )
        elif len(self.license_branding) > license_branding_maximum_length:
            raise FieldError(f"License branding has to be under {license_branding_maximum_length} characters.")
        elif self.timezone not in range(-12, 15):
            raise FieldError("Invalid timezone.")
        elif any(not char.islower() for char in self.language):
            raise FieldError("Please only use lowercase characters for guild language.")
        elif self.language not in i18n_handler.LANGUAGES or len(self.language) > language_maximum_length:
            raise FieldError("Unsupported guild language.")

        await super()._pre_save(*args, **kwargs)

    @classmethod
    async def create(cls, **kwargs) -> Model:
        reminder_activations = kwargs.pop("reminder_activations", None)
        if not reminder_activations:
            reminder_activations = await ReminderActivations.create()

        return await super().create(reminder_activations=reminder_activations, **kwargs)


class Role(Model):
    """A single role from guild.

    Role can be tiered.
    Tiers are made for the next functionality: when someone redeems a key their current role gets revoked
    and another role gets added. By adding tiers users can specify exactly which roles would
    be unique and when.

    For example roles: supporter, donator, premium_donator
    You don't want donator and premium_donator to ever be together so you would tier them.
    Since premium_donator is obviously above donator you could tier them like:
    donator tier level 1 power 1
    premium_donator tier level 1 power 2

    Now members can have supporter role along donator or premium_donator but they can't ever
    have both the donator and premium_donator at the same time.
    If member already has donator and tries to redeem premium_donator the donator will get removed and
    premium_donator will get added*. If it was the other way around and member has premium_donator and tries to
    redeem donator then nothing will happen.

    *Preserving duration:
    When upgrading tiered role you can preserve the previous duration if
    guild.preserve_previous_duration_tier_upgrade is True.
    For the above 2 cases, when member has donator role (that will last for example for another 10h)
    and tries to redeem premium_donator which will last 60 hours, if guild.preserve_previous_duration_tier_upgrade is
    True then premium_donator will last 10+60=70 hours, if it's False then it will last just 60 hours.

    For reversed case, when redeeming donator role while already having a higher tier role aka premium donator,
    duration is preserved if guild.preserve_previous_duration_tier_miss is True. Member will still only have
    premium_donator but it's duration will increase.
    """
    id = BigIntField(pk=True, generated=False, description="Role ID.")
    guild: ForeignKeyRelation[Guild] = ForeignKeyField("models.Guild", on_delete=CASCADE, related_name="roles")
    tier_level = SmallIntField(
        default=0,
        description=(
            "This represents tier for this role."
            "0 means that tiers are disabled for this role."
            "Members cannot have 2 roles from the same tier,if they do manage to redeem 2 of same tier then what will"
            "happen is that they will only get the one that has the higher tier power, other one will get deactivated."
        )
    )
    tier_power = SmallIntField(
        default=1,
        description=(
            "Used to determine role hierarchy if member is trying to claim 2 roles from the same tier level."
            "The one with higher tier power will remain while the other one will get deactivated."
        )
    )

    class Meta:
        table = "roles"
        unique_together = (("guild", "id"),)

    @classmethod
    async def get_or_create_easy(cls, guild_id: int, role_id: int) -> "Role":
        """Dunno how to make built-in get_or_create work with foreign key so using this helper.
        Below does not work:
        role = await models.Role.get_or_create(
            id=role.id,
            defaults={
                "guild__id": ctx.guild.id,
                "tier_level": tier_level,
                "tier_power": tier_power
            }
        )

        """
        try:
            return await cls.get(id=role_id)
        except DoesNotExist:
            guild = await Guild.get(id=guild_id)
            return await cls.create(guild=guild, id=role_id)

    async def _pre_save(self, *args, **kwargs) -> None:
        if not (0 <= self.tier_level <= 100):
            raise FieldError("Role tier power has to be in 0-100 range.")
        elif not (0 <= self.tier_power <= 9):
            raise FieldError("Role tier power has to be in 0-9 range.")
        elif self.tier_level != 0:  # If it's not disabled
            # Since we're accessing foreign attributes that might not yet be
            # loaded (QuerySet) we should load them just in case.
            if isinstance(self.guild, QuerySet):
                self.guild = await self.guild.first()

            if await Role.get(
                    ~Q(id=self.id),  # so it doesn't find itself and says 'hey it's a duplicate'
                    guild=self.guild,
                    tier_level=self.tier_level,
                    tier_power=self.tier_power
            ).exists():
                raise IntegrityError("Can't have 2 roles with same tier level/power!")

        await super()._pre_save(*args, **kwargs)


class AuthorizedRole(Model):
    """
    TODO: is this even needed?
    Guild owners can authorize certain roles with certain authorization level.

    Authorization level 1 can be viewed as mod permissions while level 2 can be viewed as admin
    permissions (even if the actual role does not have moderator/admin permissions).
    This is useful if you don't want to make someone mod/admin in your guild but still want them
    to use privileged bot commands.

    This class itself does not deal with which command can be used when - each command is decorated
    with decorator that specifies needed authorization level.
    """

    class AuthorizationLevel:
        moderator = 1
        administrator = 2

        @classmethod
        def is_valid(cls, authorization_level: int) -> bool:
            return 1 <= authorization_level <= 2

    role: ForeignKeyRelation[Role] = ForeignKeyField("models.Role", on_delete=CASCADE)
    guild: ForeignKeyRelation[Guild] = ForeignKeyField("models.Guild", on_delete=CASCADE)
    authorization_level = SmallIntField(
        default=AuthorizationLevel.moderator,
        description="Depending on authorization level this role can use certain privileged commands from the guild."
    )

    class Meta:
        table = "authorized_roles"
        unique_together = (("role", "guild"),)

    async def _pre_save(self, *args, **kwargs) -> None:
        if not self.AuthorizationLevel.is_valid(self.authorization_level):
            raise FieldError("Authorization level out of range.")

        # Since we're accessing foreign attributes that might not yet
        # be loaded (QuerySet) we should load them just in case.
        role_guild = self.role.guild

        if isinstance(role_guild, QuerySet):
            role_guild = await self.role.guild.first()
        if isinstance(self.guild, QuerySet):
            self.guild = await self.guild.first()

        if role_guild.id != self.guild.id:
            raise IntegrityError("Authorized role guild mismatch.")

        await super()._pre_save(*args, **kwargs)


class RolePacket(Model):
    MAXIMUM_ROLES = 20

    guild: ForeignKeyRelation[Guild] = ForeignKeyField("models.Guild", on_delete=CASCADE, related_name="packets")
    name = CharField(max_length=50)
    custom_message = CharField(
        max_length=1600,
        default="",
        description=(
            # TODO custom formatter aka <role.mention> or similar.
            "Custom message to show to member after he redeems/activates license with this role packet."
            "If empty default generic message is showed."
        )
    )
    default_role_duration = IntField(
        description=(
            "Default role duration in minutes to use on new roles that don't specifically specify their own duration."
        )
    )

    class Meta:
        table = "role_packets"
        unique_together = (("name", "guild"),)

    async def _pre_save(self, *args, **kwargs) -> None:
        max_name_length = self._meta.fields_map['name'].max_length

        if max_name_length < len(self.name):
            raise FieldError(f"Packet name has to be under {max_name_length} characters.")
        elif not self.name:
            raise FieldError("Packet name cannot be empty.")
        elif self.default_role_duration < 0:
            raise FieldError("Role packet default role duration cannot be negative.")

        await super()._pre_save(*args, **kwargs)


class PacketRole(Model):
    """Single role from role packet."""
    role: ForeignKeyRelation[Role] = ForeignKeyField("models.Role", on_delete=CASCADE)
    role_packet: ForeignKeyRelation[RolePacket] = ForeignKeyField(
        "models.RolePacket",
        on_delete=CASCADE,
        related_name="packet_roles"
    )
    duration = IntField(
        description=(
            "Duration of this role in minutes to last when redeemed."
            "Defaults to role_packet.default_role_duration if not set during creation."
        )
    )

    class Meta:
        table = "packet_roles"
        unique_together = (("role", "role_packet"),)

    @classmethod
    async def create(cls, **kwargs) -> Model:
        # If duration is not specifically specified during the creation of role packet then use the default
        # duration from role_packet.default_role_duration
        role_packet = kwargs.get("role_packet")
        duration = kwargs.pop("duration", None)
        if not duration:
            duration = role_packet.default_role_duration
        return await super().create(duration=duration, **kwargs)

    async def _pre_save(self, *args, **kwargs) -> None:
        if self.duration < 0:
            raise FieldError("Invalid duration for role.")
        # +1 since this is pre_save so it won't count this current one
        elif await self.role_packet.packet_roles.all().count() + 1 > RolePacket.MAXIMUM_ROLES:
            raise IntegrityError(
                "Cannot add packet role as number of roles in packet "
                f"would exceed limit of {RolePacket.MAXIMUM_ROLES} roles."
            )

        # Since we're accessing foreign attributes that might not yet
        # be loaded (QuerySet) we should load them just in case.
        role_guild = self.role.guild
        role_packet_guild = self.role_packet.guild

        if isinstance(role_guild, QuerySet):
            role_guild = await self.role.guild.first()
        if isinstance(role_packet_guild, QuerySet):
            role_packet_guild = await self.role_packet.guild.first()

        if role_guild.id != role_packet_guild.id:
            raise IntegrityError("Packet role fields have to point to the same guild!")

        await super()._pre_save(*args, **kwargs)


class License(Model):
    KEY_MIN_LENGTH = 14

    key = CharField(pk=True, generated=False, max_length=50)
    guild: ForeignKeyRelation[Guild] = ForeignKeyField("models.Guild", on_delete=CASCADE)
    reminder_activations = OneToOneField("models.ReminderActivations", on_delete=RESTRICT)
    inactive = BooleanField(
        default=False,
        description=(
            "Licenses that were claimed/redeemed are marked as inactive."
            "Inactive licenses should never be activated again."
        )
    )

    class Meta:
        table = "licenses"

    @classmethod
    async def create(cls, **kwargs) -> Model:
        # If not specified during the creation then use the reminder_activations from guild.reminder_activations
        reminder_activations = kwargs.pop("reminder_activations", None)  # TODO TEST
        if not reminder_activations:
            reminder_activations = await ReminderActivations.create()
        return await super().create(reminder_activations=reminder_activations, **kwargs)

    async def _post_delete(self, *args, **kwargs) -> None:
        """Deals with deleting ReminderActivations table after this table is deleted."""
        await super()._post_delete(*args, **kwargs)  # TODO TEST THIS
        await self.reminder_activations.delete()

    async def _pre_save(self, *args, **kwargs) -> None:
        if len(self.key) < self.KEY_MIN_LENGTH:
            raise FieldError(f"License key has to be longer than {self.KEY_MIN_LENGTH} characters.")

        await super()._pre_save(*args, **kwargs)


class MultipleUseLicense(License):
    MAXIMUM_USES_LEFT = 1_000_000

    uses_left = SmallIntField(
        default=1,
        description=(
            "Number of times this same license can be used (useful example for giveaways)."
            "Value of 0 marks this license as deactivated and it cannot be redeemed again."
        )
    )

    async def _pre_save(self, *args, **kwargs) -> None:
        if self.uses_left < 0:
            raise FieldError("License number of uses cannot be negative.")
        elif self.uses_left > self.MAXIMUM_USES_LEFT:
            raise FieldError("License number of uses is too big.")

        await super()._pre_save(*args, **kwargs)


class RegeneratingLicense(License):
    role_packet: ForeignKeyRelation[RolePacket] = ForeignKeyField(
        "models.RolePacket",
        on_delete=CASCADE,  # TODO when deleting role packet check if there is a relationship and warn member
        description=(
            "When all roles from license expire and the license is set as regenerating we will"
            "know which roles to re-add. Note that if the role_packet changes in the meantime it"
            "is possible the new roles will be different from previous ones."
        )
    )

    async def regenerate(self) -> "RegeneratingLicense":
        """Deals with regenerating licenses by creating a new licenses that has the same data as this one.

        Creates new license column with new key.
        Also copies reminder_activations data from previous license and creates new  reminder_activations table
        with that data since it is OneToOneField.
        Marks the previous license as inactive.
        """
        # Since we're accessing foreign attributes that might not yet
        # be loaded (QuerySet) we should load them just in case.
        guild = self.guild
        reminder_activations = self.reminder_activations
        role_packet = self.role_packet

        if isinstance(guild, QuerySet):
            guild = await self.guild.first()
        if isinstance(reminder_activations, QuerySet):
            reminder_activations = await self.reminder_activations.first()
        if isinstance(role_packet, QuerySet):
            role_packet = await self.role_packet.first()

        new_key = LicenseFormatter.generate_single(guild.custom_license_format, guild.license_branding)
        new_reminder_activations = await reminder_activations.create_easy(*reminder_activations.get_all_activations())
        # clone does not work in all cases, even when specifying the new key. So creating directly..
        new_license = RegeneratingLicense(
            key=new_key, guild=guild, reminder_activations=new_reminder_activations, role_packet=role_packet
        )
        await new_license.save()

        self.inactive = True
        await self.save()

        return new_license


class LicensedMember(Model):
    member_id = BigIntField()
    license: ForeignKeyRelation[License] = ForeignKeyField("models.License", on_delete=CASCADE)

    class Meta:
        table = "licensed_members"
        unique_together = (("member_id", "license"),)


class LicensedRole(Model):
    role: ForeignKeyRelation[Role] = ForeignKeyField("models.Role", on_delete=CASCADE)
    licensed_member: ForeignKeyRelation[LicensedMember] = ForeignKeyField("models.LicensedMember", on_delete=CASCADE)
    expiration = DatetimeField(null=True)

    class Meta:
        table = "licensed_roles"
        unique_together = (("role", "licensed_member"),)


class Reminder(Model):
    activation = BigIntField(
        description=(
            "This represents amount of minutes to send the reminder before license expiration."
            "For example if the license duration is 10_080 minutes (aka 7 days) and reminder is set to 80 then "
            "reminder will be sent exactly after 10_000 minutes pass."
        )
    )
    sent = BooleanField(
        default=False,
        description=(
            "Was this reminder sent to user or not."
            "We don't want to spam the user with reminders once activation activates."
        )
    )
    licensed_member: ForeignKeyRelation[LicensedMember] = ForeignKeyField(
        "models.LicensedMember",
        on_delete=CASCADE,
        description="Member who is going to be reminded about his license expiring."
    )

    class Meta:
        table = "reminders"
        unique_together = (("activation", "licensed_member"),)
