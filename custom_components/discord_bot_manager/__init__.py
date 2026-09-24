"""Discord Bot Manager integration for Home Assistant.

Simplified config: on new instance creation, only server ID and bot token are
required. All command management happens via services and a custom Lovelace panel.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    COMMAND_NAME_REGEX,
    CONF_COMMAND,
    CONF_COMMANDS,
    CONF_DESCRIPTION,
    CONF_GUILD_ID,
    CONF_TOKEN,
    DOMAIN,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

REGEX_COMMAND = re.compile(COMMAND_NAME_REGEX)


def sanitize_command_name(raw: str) -> str | None:
    """Clean a Discord slash command name to ^[a-z0-9_-]{1,32}$.

    Returns ``None`` when no valid name can be derived.
    """
    name = re.sub(r"[^a-z0-9_-]", "_", (raw or "").strip().lower())
    name = re.sub(r"_+", "_", name).strip("_-")
    name = name[:32].rstrip("_-")
    if not name or not REGEX_COMMAND.match(name):
        return None
    return name


class HADiscordBotManager:
    """Manage one Discord bot instance tied to a config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.client: discord.Client | None = None
        self.tree: discord.app_commands.CommandTree | None = None
        self._start_task: asyncio.Task | None = None
        self._guild_id: int | None = None
        self._labels: list[str] = []

        guild_id = str(entry.data.get(CONF_GUILD_ID, "") or "").strip()
        if guild_id.isdigit():
            self._guild_id = int(guild_id)

        self._labels = list(entry.data.get("labels", []) or [])

    @property
    def entry_id(self) -> str:
        """Return the config entry ID."""
        return self.entry.entry_id

    def get_config(self) -> dict[str, Any]:
        """Return full configuration as a serializable dict."""
        commands = self.get_commands()
        return {
            "entry_id": self.entry.entry_id,
            "bot_name": self.entry.data.get("bot_name", ""),
            "guild_id": self.entry.data.get("guild_id", ""),
            "token_masked": self._mask_token(
                str(self.entry.data.get(CONF_TOKEN, ""))
            ),
            "labels": self.get_labels(),
            "commands": commands,
            "total_commands": len(commands),
            "status": self._get_status(),
            "last_sync": self.entry.data.get("last_sync", ""),
        }

    @staticmethod
    def _mask_token(token: str) -> str:
        """Return masked token (first 10 chars visible, rest hidden)."""
        if len(token) <= 10:
            return token + "..."
        return token[:10] + "..."

    def get_commands(self) -> list[dict[str, Any]]:
        """Return configured commands list."""
        return list(self.entry.data.get(CONF_COMMANDS, []) or [])

    def get_labels(self) -> list[str]:
        """Return configured labels."""
        return list(self._labels)

    def add_command(self, command: str, description: str = "", format: str = "{{ states(entity_id) }}", entity_id: str | None = None) -> None:
        """Add a command to the bot's configuration."""
        sanitized = sanitize_command_name(command)
        if not sanitized:
            _LOGGER.warning("Invalid command name: %s", command)
            return

        commands = self.get_commands()
        for cmd in commands:
            if cmd.get("command") == sanitized:
                _LOGGER.warning("Command %s already exists", sanitized)
                return

        commands.append({
            "entity_id": entity_id or "",
            "command": sanitized,
            "description": description,
            "format": format,
        })
        self._update_entry_data({CONF_COMMANDS: commands})

    def remove_command(self, command: str) -> None:
        """Remove a command from the bot's configuration."""
        sanitized = sanitize_command_name(command)
        if not sanitized:
            return

        commands = [c for c in self.get_commands() if c.get("command") != sanitized]
        self._update_entry_data({CONF_COMMANDS: commands})

    def update_command(self, command: str, description: str = "", format: str = "", entity_id: str | None = None) -> None:
        """Update an existing command's attributes."""
        sanitized = sanitize_command_name(command)
        if not sanitized:
            return

        commands = self.get_commands()
        for idx, cmd in enumerate(commands):
            if cmd.get("command") == sanitized:
                if description:
                    commands[idx]["description"] = description
                if format:
                    commands[idx]["format"] = format
                if entity_id:
                    commands[idx]["entity_id"] = entity_id
                break
        self._update_entry_data({CONF_COMMANDS: commands})

    def add_label(self, label: str) -> None:
        """Add a label to the bot's configuration."""
        label = label.strip()
        if not label or label in self._labels:
            return
        self._labels.append(label)
        self._update_entry_data({"labels": list(self._labels)})

    def remove_label(self, label: str) -> None:
        """Remove a label from the bot's configuration."""
        label = label.strip()
        if label in self._labels:
            self._labels.remove(label)
            self._update_entry_data({"labels": list(self._labels)})

    def _update_entry_data(self, data: dict[str, Any]) -> None:
        """Update config entry data and save timestamp."""
        data = {**self.entry.data, **data}
        from datetime import datetime
        data["last_sync"] = datetime.now().isoformat()
        self.hass.config_entries.async_update_entry(self.entry, data=data)

    def _get_status(self) -> str:
        """Return current bot status."""
        if not self.client:
            return "offline"
        if self.client.is_ready():
            return "online"
        return "connecting"

    async def async_sync_commands(self) -> None:
        """Sync commands to Discord."""
        if self.tree is None:
            return

        commands = self.get_commands()
        used_names: set[str] = set()

        # Clear existing commands from tree
        self.tree.clear_commands()

        for cmd_cfg in commands:
            cmd_name = cmd_cfg.get("command", "")
            if not cmd_name:
                continue
            if cmd_name in used_names:
                continue
            used_names.add(cmd_name)

            # Create dynamic callback based on command type
            entity_id = cmd_cfg.get("entity_id", "")
            description = cmd_cfg.get("description", f"Commande '{cmd_name}'")

            if entity_id:
                async def _run_cmd(interaction: discord.Interaction, e_id=entity_id, fmt=cmd_cfg.get("format", "{{ states(entity_id) }}")) -> None:
                    await self._async_send_entity_state(interaction, e_id, fmt)

                tree_cmd = discord.app_commands.Command(
                    name=cmd_name,
                    description=description[:100],
                    callback=_run_cmd,
                )
            else:
                async def _run_cmd(interaction: discord.Interaction) -> None:
                    await interaction.response.send_message(
                        f"Commande `{cmd_name}` exécutée.", ephemeral=True
                    )

                tree_cmd = discord.app_commands.Command(
                    name=cmd_name,
                    description=description[:100],
                    callback=_run_cmd,
                )

            self.tree.add_command(tree_cmd)

        # Sync to guild or globally
        guild = discord.Object(id=self._guild_id) if self._guild_id else None
        try:
            if guild:
                await self.tree.sync(guild=guild)
                _LOGGER.info("Commands synced to guild %s", self._guild_id)
            else:
                await self.tree.sync()
                _LOGGER.info("Commands synced globally")
        except discord.HTTPException as err:
            _LOGGER.error("Failed to sync commands: %s", err)

        # Update last_sync
        from datetime import datetime
        self._update_entry_data({"last_sync": datetime.now().isoformat()})

    async def async_start(self) -> None:
        """Create the Discord client and start it in the background."""
        token = str(self.entry.data.get(CONF_TOKEN, "") or "").strip()
        commands = self.get_commands()

        if not token:
            _LOGGER.error("Discord bot token is required for %s", self.entry.title)
            return

        intents = discord.Intents.default()
        manager = self

        class _Client(discord.Client):
            """Discord client wiring commands."""

            def __init__(self) -> None:
                super().__init__(intents=intents)
                self.tree = discord.app_commands.CommandTree(self)

            async def setup_hook(self) -> None:
                """Register slash commands and sync."""
                await manager.async_sync_commands()

            async def on_ready(self) -> None:
                assert self.user is not None
                _LOGGER.info("Discord bot connected as %s", self.user)

            async def on_error(self, event, *args, **kwargs) -> None:
                _LOGGER.exception("Discord error in event %s", event)

        self.client = _Client()
        self.tree = self.client.tree  # type: ignore[attr-defined]

        self._start_task = self.hass.async_create_background_task(
            self.client.start(token),
            name=f"{DOMAIN}_{self.entry.entry_id}",
        )

    async def _async_send_entity_state(
        self,
        interaction: discord.Interaction,
        entity_id: str,
        format_str: str,
    ) -> None:
        """Send the Jinja2-rendered state of an entity for a slash command."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        state = self.hass.states.get(entity_id)
        if state is None:
            await interaction.followup.send(
                f"❌ Entité `{entity_id}` introuvable.", ephemeral=True
            )
            return

        from homeassistant.helpers.template import Template
        try:
            tpl = Template(format_str, self.hass)
            rendered = tpl.async_render({
                "state": state.state,
                "attributes": dict(state.attributes),
                "entity_id": entity_id,
                "entity": state,
            })
            await interaction.followup.send(str(rendered)[:2000])
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Template rendering failed for %s", entity_id)
            await interaction.followup.send(
                f"❌ Erreur de template : {err}", ephemeral=True
            )

    async def async_stop(self) -> None:
        """Stop the Discord client and clean up."""
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None

        if self.client:
            try:
                await self.client.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error while closing Discord client", exc_info=True)
            self.client = None
        self.tree = None


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Discord Bot Manager from YAML configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discord Bot Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if not str(entry.data.get(CONF_TOKEN, "")).strip():
        _LOGGER.error("Missing Discord bot token for entry %s", entry.title)
        return False

    await async_setup_services(hass)

    manager = HADiscordBotManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager

    try:
        await manager.async_start()
    except discord.PrivilegedIntentsRequired:
        raise ConfigEntryNotReady("Discord privileged intents required")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to connect bot: %s", err)
        raise ConfigEntryNotReady(f"Failed to connect: {err}")

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry (disconnect the bot cleanly)."""
    manager: HADiscordBotManager | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if manager:
        await manager.async_stop()

    # Unload platforms
    return await hass.config_entries.async_forward_entry_unload(entry, Platform.SENSOR)
