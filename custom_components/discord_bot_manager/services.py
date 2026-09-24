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
        """Re-sync the Discord command tree and re-scan for new commands."""
        entry_filter = call.data.get("entry_id")
        async for manager in _iter_managers(entry_filter):
            # Re-sync discord commands
            if manager.tree is not None:
                guild_id = manager._guild_id
                try:
                    import discord
                    if guild_id:
                        await manager.tree.sync(
                            guild=discord.Object(id=guild_id)
                        )
                    else:
                        await manager.tree.sync()
                    _LOGGER.info("Command tree re-synced for %s", entry_filter or "all")
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Failed to re-sync command tree")
            
            # Re-scan for new commands based on current labels
            entry = manager.entry
            labels = entry.data.get("labels", []) or entry.data.get("automation_labels", [])
            
            if labels:
                # Import the scan function
                from homeassistant.helpers import entity_registry as er
                from . import sanitize_command_name
                from .const import CONF_COMMAND, CONF_DESCRIPTION, CONF_FORMAT, CONF_ENTITIES
                
                entity_registry = er.async_get(manager.hass)
                all_commands = []
                
                # Find automations
                for entity_entry in entity_registry.entities.values():
                    if entity_entry.domain == "automation":
                        entity_labels = set(entity_entry.labels)
                        if any(label in entity_labels for label in labels):
                            state = manager.hass.states.get(entity_entry.entity_id)
                            friendly_name = (
                                state.attributes.get("friendly_name", entity_entry.entity_id)
                                if state
                                else entity_entry.entity_id
                            )
                            all_commands.append({
                                "entity_id": entity_entry.entity_id,
                                "command": sanitize_command_name(entity_entry.entity_id.split(".", 1)[-1]) or entity_entry.entity_id.split(".", 1)[-1],
                                "description": f"Déclenche '{friendly_name}'",
                                "format": f"✅ Automatisation `{entity_entry.entity_id}` déclenchée.",
                            })
                
                # Find entities
                for entity_entry in entity_registry.entities.values():
                    if entity_entry.domain != "automation":
                        entity_labels = set(entity_entry.labels)
                        if any(label in entity_labels for label in labels):
                            all_commands.append({
                                "entity_id": entity_entry.entity_id,
                                "command": sanitize_command_name(entity_entry.entity_id.split(".", 1)[-1]) or entity_entry.entity_id.split(".", 1)[-1],
                                "description": f"Affiche l'état de {entity_entry.name or entity_entry.entity_id}",
                                "format": "{{ states(entity_id) }}",
                            })
                
                # Update entry with new commands
                updated_data = {
                    **entry.data,
                    CONF_ENTITIES: all_commands,
                }
                manager.hass.config_entries.async_update_entry(entry, data=updated_data)
                
                # Reload to apply changes
                await manager.hass.config_entries.async_reload(entry.entry_id)
                
                _LOGGER.info("Re-scanned and updated %d commands for %s", len(all_commands), entry_filter or "all")

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
