"""Constants for the Discord Bot Manager integration."""

DOMAIN = "discord_bot_manager"

CONF_TOKEN = "token"
CONF_GUILD_ID = "guild_id"
CONF_LABELS = "labels"
CONF_ENTITIES = "entities"
CONF_BOTS = "bots"
CONF_COMMAND = "command"
CONF_DESCRIPTION = "description"
CONF_FORMAT = "format"
CONF_AUTOMATION_LABELS = "automation_labels"

DEFAULT_COMMAND_PREFIX = ""

COMMAND_NAME_REGEX = r"^[a-z0-9_-]{1,32}$"
