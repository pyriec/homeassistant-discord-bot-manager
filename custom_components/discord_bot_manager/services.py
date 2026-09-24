"""Discord Bot Manager services."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_REFRESH_COMMANDS = "refresh_commands"
SERVICE_RECONNECT = "reconnect"

REFRESH_COMMANDS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Discord Bot Manager services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_COMMANDS):
        return

    async def _iter_managers(entry_filter: str | None):
        for entry_id, manager in hass.data.get(DOMAIN, {}).items():
            if entry_filter and entry_id != entry_filter:
                continue
            yield manager

    async def async_handle_refresh_commands(call: ServiceCall) -> None:
        """Re-sync the Discord command tree."""
        entry_filter = call.data.get("entry_id")
        async for manager in _iter_managers(entry_filter):
            if manager.tree is None:
                continue
            guild_id = manager._guild_id
            try:
                if guild_id:
                    await manager.tree.sync(
                        guild=__import__("discord").Object(id=guild_id)
                    )
                else:
                    await manager.tree.sync()
                _LOGGER.info("Command tree re-synced for %s", entry_filter or "all")
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to re-sync command tree")

    async def async_handle_reconnect(call: ServiceCall) -> None:
        """Stop and restart the bot(s)."""
        entry_filter = call.data.get("entry_id")
        for entry_id in list(hass.data.get(DOMAIN, {})):
            if entry_filter and entry_id != entry_filter:
                continue
            await hass.config_entries.async_reload(entry_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_COMMANDS,
        async_handle_refresh_commands,
        schema=REFRESH_COMMANDS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT,
        async_handle_reconnect,
        schema=REFRESH_COMMANDS_SCHEMA,
    )
