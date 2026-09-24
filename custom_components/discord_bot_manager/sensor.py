"""Discord Bot Manager sensor platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DiscordBotManagerSensor(SensorEntity):
    """Status sensor for a Discord bot."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manager: Any) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "Statut du bot"
        self._attr_icon = "mdi:discord-horizontal"
        self._attr_native_value = "unknown"
        self._attr_extra_state_attributes: dict[str, Any] = {
            "connection": "offline",
            "guild_id": entry.data.get("guild_id", ""),
            "bot_name": entry.data.get("bot_name", ""),
            "commands": [],
            "labels": [],
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
        from datetime import datetime

        if not self._manager or not self._manager.client:
            self._attr_native_value = "offline"
            self._attr_icon = "mdi:discord-horizontal"
            self._attr_extra_state_attributes["connection"] = "offline"
        elif self._manager.client.is_ready():
            self._attr_native_value = "online"
            self._attr_icon = "mdi:discord"
            self._attr_extra_state_attributes["connection"] = "online"
            if self._manager.client.user:
                self._attr_extra_state_attributes["bot_name"] = str(
                    self._manager.client.user
                )
        else:
            self._attr_native_value = "connecting"
            self._attr_icon = "mdi:discord"
            self._attr_extra_state_attributes["connection"] = "connecting"

        commands = self._manager.get_commands()
        self._attr_extra_state_attributes["commands"] = commands
        self._attr_extra_state_attributes["total_commands"] = len(commands)

        labels = self._manager.get_labels()
        self._attr_extra_state_attributes["labels"] = labels

        self._attr_extra_state_attributes["last_updated"] = datetime.now().isoformat()

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Discord Bot Manager sensor."""
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        sensor = DiscordBotManagerSensor(hass, entry, manager)
        async_add_entities([sensor])
        _LOGGER.info("Sensor added for entry %s", entry.entry_id)
