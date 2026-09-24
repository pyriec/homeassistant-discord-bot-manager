"""Discord Bot Manager entity platform - Status dashboard."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DiscordBotDashboardSensor(SensorEntity):
    """Dashboard sensor showing bot status and commands."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manager: Any) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_dashboard"
        self._attr_name = "Tableau de bord Discord"
        self._attr_icon = "mdi:discord"
        self._attr_native_value = "unknown"
        self._attr_extra_state_attributes: dict[str, Any] = {
            "status": "unknown",
            "guild_id": entry.data.get("guild_id", ""),
            "labels": entry.data.get("labels", []),
            "automation_commands": [],
            "entity_commands": [],
            "total_commands": 0,
            "last_updated": "",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._manager is not None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self._entry.add_update_listener(self._on_entry_updated)
        )
        await self.async_update()

    async def _on_entry_updated(self) -> None:
        """Handle entry updates."""
        await self.async_update()

    async def async_update(self) -> None:
        """Update the sensor state."""
        # Bot connection status
        if not self._manager or not self._manager.client:
            self._attr_native_value = "offline"
            self._attr_icon = "mdi:discord-horizontal"
            self._attr_extra_state_attributes["status"] = "offline"
        elif self._manager.client.is_ready():
            self._attr_native_value = "online"
            self._attr_icon = "mdi:discord"
            self._attr_extra_state_attributes["status"] = "online"
            if self._manager.client.user:
                self._attr_extra_state_attributes["bot_name"] = str(self._manager.client.user)
        else:
            self._attr_native_value = "connecting"
            self._attr_icon = "mdi:discord"
            self._attr_extra_state_attributes["status"] = "connecting"

        # Get configured labels
        labels = self._entry.data.get("labels", [])
        self._attr_extra_state_attributes["labels"] = labels

        # Get automation commands
        automation_commands = []
        if hasattr(self._manager, '_async_get_labeled_automations'):
            automation_ids = self._manager._async_get_labeled_automations(
                self._entry.data.get("automation_labels", labels)
            )
            for aid in automation_ids:
                state = self._hass.states.get(aid)
                friendly = (
                    state.attributes.get("friendly_name", aid)
                    if state
                    else aid
                )
                automation_commands.append({
                    "entity_id": aid,
                    "command": aid.split(".", 1)[-1],
                    "friendly_name": friendly,
                    "description": f"Déclenche '{friendly}'",
                })
        self._attr_extra_state_attributes["automation_commands"] = automation_commands

        # Get entity commands
        entity_commands = []
        for cfg in self._entry.data.get("entities", []):
            entity_commands.append({
                "entity_id": cfg.get("entity_id", ""),
                "command": cfg.get("command", ""),
                "description": cfg.get("description", ""),
            })
        self._attr_extra_state_attributes["entity_commands"] = entity_commands

        # Total commands
        total = len(automation_commands) + len(entity_commands)
        self._attr_extra_state_attributes["total_commands"] = total

        # Timestamp
        from datetime import datetime
        self._attr_extra_state_attributes["last_updated"] = datetime.now().isoformat()

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Discord Bot Manager dashboard sensor."""
    from . import DOMAIN as DOMAIN_NAME

    manager = hass.data.get(DOMAIN_NAME, {}).get(entry.entry_id)
    if manager:
        sensor = DiscordBotDashboardSensor(hass, entry, manager)
        async_add_entities([sensor])
        _LOGGER.info("Dashboard sensor added for entry %s", entry.entry_id)
