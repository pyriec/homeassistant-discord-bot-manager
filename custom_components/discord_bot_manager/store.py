"""Persistent storage for Discord Bot Manager configurations."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "discord_bot_manager"


class DiscordBotStore:
    """Manage persistent bot configurations."""

    def __init__(self, hass) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        data = await self._store.async_load()
        if data is None:
            data = {"bots": {}}
        self._data = data
        return self._data

    async def async_save(self) -> None:
        """Save data to storage."""
        self._data.setdefault("bots", {})
        await self._store.async_save(self._data)

    def get_bots(self) -> dict[str, Any]:
        """Get all bot configurations."""
        return self._data.get("bots", {})

    def get_bot(self, entry_id: str) -> dict[str, Any] | None:
        """Get a specific bot configuration."""
        return self._data.get("bots", {}).get(entry_id)

    async def async_save_bot(self, entry_id: str, bot_data: dict[str, Any]) -> None:
        """Save a bot configuration."""
        bots = self._data.setdefault("bots", {})
        bots[entry_id] = bot_data
        await self.async_save()

    async def async_delete_bot(self, entry_id: str) -> None:
        """Delete a bot configuration."""
        bots = self._data.get("bots", {})
        bots.pop(entry_id, None)
        await self.async_save()