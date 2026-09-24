"""Discord Bot Manager services."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_BOT_NAME,
    CONF_COMMAND,
    CONF_COMMANDS,
    CONF_DESCRIPTION,
    CONF_ENTITY_ID,
    CONF_FORMAT,
    CONF_GUILD_ID,
    CONF_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_CONFIG = "get_config"
SERVICE_UPDATE_COMMAND = "update_command"
SERVICE_ADD_COMMAND = "add_command"
SERVICE_REMOVE_COMMAND = "remove_command"
SERVICE_ADD_LABEL = "add_label"
SERVICE_REMOVE_LABEL = "remove_label"
SERVICE_CREATE_LABEL = "create_label"
SERVICE_REFRESH_COMMANDS = "refresh_commands"
SERVICE_RECONNECT = "reconnect"

GET_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
    }
)

UPDATE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("command"): str,
        vol.Optional("description", default=""): str,
        vol.Optional("format", default="{{ states(entity_id) }}"): str,
        vol.Optional("entity_id"): str,
    }
)

ADD_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("command"): str,
        vol.Optional("description", default=""): str,
        vol.Optional("format", default="{{ states(entity_id) }}"): str,
        vol.Optional("entity_id"): str,
    }
)

REMOVE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("command"): str,
    }
)

ADD_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("label"): str,
    }
)

REMOVE_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("label"): str,
    }
)

CREATE_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required("label"): str,
    }
)

REFRESH_COMMANDS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Discord Bot Manager services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_CONFIG):
        return

    async def _get_manager(entry_id: str):
        return hass.data.get(DOMAIN, {}).get(entry_id)

    async def _update_entry_data(entry_id: str, **kwargs) -> None:
        """Update config entry data fields."""
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return
        new_data = dict(entry.data)
        new_data.update(kwargs)
        hass.config_entries.async_update_entry(entry, data=new_data)

    async def async_handle_get_config(call: ServiceCall) -> dict[str, Any]:
        """Return full configuration for a bot."""
        entry_id = call.data.get("entry_id")
        manager = await _get_manager(entry_id)
        if manager is None:
            return {}
        return manager.get_config()

    async def async_handle_update_command(call: ServiceCall) -> None:
        """Update an existing command's description/format."""
        entry_id = call.data["entry_id"]
        command = call.data["command"]
        manager = await _get_manager(entry_id)
        if manager is None:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return
        manager.update_command(
            command=command,
            description=call.data.get("description", ""),
            format=call.data.get("format", "{{ states(entity_id) }}"),
            entity_id=call.data.get("entity_id"),
        )
        await manager.async_save()

    async def async_handle_add_command(call: ServiceCall) -> None:
        """Add a new command to a bot."""
        entry_id = call.data["entry_id"]
        command = call.data["command"]
        manager = await _get_manager(entry_id)
        if manager is None:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return
        manager.add_command(
            command=command,
            description=call.data.get("description", ""),
            format=call.data.get("format", "{{ states(entity_id) }}"),
            entity_id=call.data.get("entity_id"),
        )
        await manager.async_save()

    async def async_handle_remove_command(call: ServiceCall) -> None:
        """Remove a command from a bot."""
        entry_id = call.data["entry_id"]
        command = call.data["command"]
        manager = await _get_manager(entry_id)
        if manager is None:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return
        manager.remove_command(command)
        await manager.async_save()

    async def async_handle_add_label(call: ServiceCall) -> None:
        """Add a label to a bot's configuration."""
        entry_id = call.data["entry_id"]
        label = call.data["label"]
        manager = await _get_manager(entry_id)
        if manager is None:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return
        manager.add_label(label)
        await manager.async_save()

    async def async_handle_remove_label(call: ServiceCall) -> None:
        """Remove a label from a bot's configuration."""
        entry_id = call.data["entry_id"]
        label = call.data["label"]
        manager = await _get_manager(entry_id)
        if manager is None:
            _LOGGER.error("Unknown entry_id: %s", entry_id)
            return
        manager.remove_label(label)
        await manager.async_save()

    async def async_handle_create_label(call: ServiceCall) -> None:
        """Create a new HA label."""
        label = call.data["label"]
        try:
            from homeassistant.helpers import label_registry as lr
            registry = lr.async_get(hass)
            registry.async_create_label(label)
            _LOGGER.info("Created label '%s'", label)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to create label '%s': %s", label, err)

    async def async_handle_refresh_commands(call: ServiceCall) -> None:
        """Re-sync the Discord command tree."""
        entry_filter = call.data.get("entry_id")
        for entry_id, manager in hass.data.get(DOMAIN, {}).items():
            if entry_filter and entry_id != entry_filter:
                continue
            await manager.async_sync_commands()

    async def async_handle_reconnect(call: ServiceCall) -> None:
        """Stop and restart the bot(s)."""
        entry_filter = call.data.get("entry_id")
        for entry_id in list(hass.data.get(DOMAIN, {})):
            if entry_filter and entry_id != entry_filter:
                continue
            await hass.config_entries.async_reload(entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_CONFIG, async_handle_get_config, schema=GET_CONFIG_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_COMMAND, async_handle_update_command, schema=UPDATE_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_COMMAND, async_handle_add_command, schema=ADD_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_COMMAND, async_handle_remove_command, schema=REMOVE_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_LABEL, async_handle_add_label, schema=ADD_LABEL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_LABEL, async_handle_remove_label, schema=REMOVE_LABEL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_LABEL, async_handle_create_label, schema=CREATE_LABEL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH_COMMANDS, async_handle_refresh_commands, schema=REFRESH_COMMANDS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RECONNECT, async_handle_reconnect, schema=REFRESH_COMMANDS_SCHEMA
    )