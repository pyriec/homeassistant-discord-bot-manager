"""Constants for the Discord Bot Manager integration."""

DOMAIN = "discord_bot_manager"

# Config entry keys
CONF_TOKEN = "token"
CONF_GUILD_ID = "guild_id"
CONF_BOT_NAME = "bot_name"
CONF_COMMANDS = "commands"
CONF_COMMAND = "command"
CONF_DESCRIPTION = "description"
CONF_FORMAT = "format"
CONF_ENTITY_ID = "entity_id"
CONF_LABELS = "labels"
CONF_AUTOMATION_LABELS = "automation_labels"

# Service keys
SERVICE_GET_CONFIG = "get_config"
SERVICE_UPDATE_COMMAND = "update_command"
SERVICE_ADD_COMMAND = "add_command"
SERVICE_REMOVE_COMMAND = "remove_command"
SERVICE_ADD_LABEL = "add_label"
SERVICE_REMOVE_LABEL = "remove_label"
SERVICE_CREATE_LABEL = "create_label"
SERVICE_REFRESH_COMMANDS = "refresh_commands"
SERVICE_RECONNECT = "reconnect"

DEFAULT_COMMAND_PREFIX = ""

COMMAND_NAME_REGEX = r"^[a-z0-9_-]{1,32}$"