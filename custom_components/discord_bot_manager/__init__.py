"""Discord Bot Manager integration for Home Assistant.

Runs one or more persistent Discord bots, exposing:

- Home Assistant automations (matched by HA labels) as Discord slash commands.
- Configured entity states as slash commands with Jinja2 template rendering.
- Dashboard sensor showing bot status and configured commands.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template

from .const import (
    COMMAND_NAME_REGEX,
    CONF_AUTOMATION_LABELS,
    CONF_BOTS,
    CONF_COMMAND,
    CONF_DESCRIPTION,
    CONF_ENTITIES,
    CONF_FORMAT,
    CONF_GUILD_ID,
    CONF_LABELS,
    CONF_TOKEN,
    DOMAIN,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

ENTITY_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_DESCRIPTION, default=""): cv.string,
        vol.Optional(CONF_FORMAT, default="{{ states(entity_id) }}"): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_BOTS, default=[]): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_TOKEN): cv.string,
                                vol.Optional(CONF_GUILD_ID): cv.string,
                                vol.Optional(
                                    CONF_LABELS, default=[]
                                ): vol.All(cv.ensure_list, [cv.string]),
                                vol.Optional(
                                    CONF_AUTOMATION_LABELS, default=[]
                                ): vol.All(cv.ensure_list, [cv.string]),
                                vol.Optional(
                                    CONF_ENTITIES, default=[]
                                ): vol.All(cv.ensure_list, [ENTITY_COMMAND_SCHEMA]),
                            }
                        )
                    ],
                )
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

REGEX_COMMAND = re.compile(COMMAND_NAME_REGEX)


def sanitize_command_name(raw: str) -> str | None:
    """Clean a Discord slash command name to ``^[a-z0-9_-]{1,32}$``.

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

        guild_id = str(entry.data.get(CONF_GUILD_ID, "") or "").strip()
        if guild_id.isdigit():
            self._guild_id = int(guild_id)

    async def async_start(self) -> None:
        """Create the Discord client and start it in the background."""
        token = str(self.entry.data.get(CONF_TOKEN, "")).strip()
        automation_labels: list[str] = list(
            self.entry.data.get(CONF_AUTOMATION_LABELS)
            or self.entry.data.get(CONF_LABELS)
            or []
        )
        entities: list[dict[str, Any]] = list(
            self.entry.data.get(CONF_ENTITIES) or []
        )

        if not token:
            _LOGGER.error("Discord bot token is required for %s", self.entry.title)
            return

        intents = discord.Intents.default()
        manager = self

        class _Client(discord.Client):
            """Discord client wiring automation/entity slash commands."""

            def __init__(self) -> None:
                super().__init__(intents=intents)
                self.tree = discord.app_commands.CommandTree(self)

            async def setup_hook(self) -> None:
                """Register slash commands and sync the command tree."""
                await manager.async_register_commands(
                    self.tree, automation_labels, entities
                )
                guild = (
                    discord.Object(id=manager._guild_id)
                    if manager._guild_id
                    else None
                )
                try:
                    if guild is not None:
                        await self.tree.sync(guild=guild)
                        _LOGGER.info(
                            "Slash commands synced to guild %s", manager._guild_id
                        )
                    else:
                        await self.tree.sync()
                        _LOGGER.info(
                            "Slash commands synced globally (may take up to 1h)"
                        )
                except discord.HTTPException as err:
                    _LOGGER.error("Failed to sync slash commands: %s", err)

            async def on_ready(self) -> None:
                assert self.user is not None
                _LOGGER.info("Discord bot connected as %s", self.user)

            async def on_error(self, event, *args, **kwargs) -> None:
                _LOGGER.exception("Discord error in event %s", event)

        self.client = _Client()
        self.tree = self.client.tree  # type: ignore[attr-defined]

        # Start the Discord gateway loop without blocking Home Assistant.
        self._start_task = self.hass.async_create_background_task(
            self.client.start(token),
            name=f"{DOMAIN}_{self.entry.entry_id}",
        )

    async def async_register_commands(
        self,
        tree: discord.app_commands.CommandTree,
        automation_labels: list[str],
        entities: list[dict[str, Any]],
    ) -> None:
        """Register automation and entity slash commands on the tree."""
        automation_ids = self._async_get_labeled_automations(automation_labels)
        used_names: set[str] = set()

        for automation_id in automation_ids:
            name = sanitize_command_name(automation_id.split(".", 1)[-1])
            if not name:
                _LOGGER.warning(
                    "Skipping automation with invalid id: %s", automation_id
                )
                continue
            if name in used_names:
                _LOGGER.warning(
                    "Duplicate slash command name '%s' (automation %s), skipping",
                    name,
                    automation_id,
                )
                continue

            state = self.hass.states.get(automation_id)
            friendly = (
                state.attributes.get("friendly_name", name) if state else name
            )
            used_names.add(name)

            def _make_automation_callback(aid: str):
                async def _run(interaction: discord.Interaction) -> None:
                    await self._async_trigger_automation(interaction, aid)

                return _run

            tree.add_command(
                discord.app_commands.Command(
                    name=name,
                    description=f"Déclenche l'automatisation « {friendly} »"[:100],
                    callback=_make_automation_callback(automation_id),
                )
            )

        for entity_cfg in entities:
            entity_id = entity_cfg.get("entity_id", "")
            name = sanitize_command_name(entity_cfg.get(CONF_COMMAND, ""))
            if not name:
                _LOGGER.warning(
                    "Skipping entity command with invalid name: %s (%s)",
                    entity_cfg.get(CONF_COMMAND),
                    entity_id,
                )
                continue
            if name in used_names:
                _LOGGER.warning("Duplicate slash command name '%s', skipping", name)
                continue
            used_names.add(name)

            def _make_entity_callback(eid: str, fmt: str):
                async def _run(interaction: discord.Interaction) -> None:
                    await self._async_send_entity_state(interaction, eid, fmt)

                return _run

            tree.add_command(
                discord.app_commands.Command(
                    name=name,
                    description=(
                        entity_cfg.get(CONF_DESCRIPTION)
                        or f"Affiche l'état de {entity_id}"
                    )[:100],
                    callback=_make_entity_callback(
                        entity_id,
                        entity_cfg.get(CONF_FORMAT, "{{ states(entity_id) }}"),
                    ),
                )
            )

        _LOGGER.info(
            "Registered %d automation and %d entity slash commands",
            len(automation_ids),
            len(entities),
        )

    def _async_get_labeled_automations(self, labels: list[str]) -> list[str]:
        """Return automation entity ids carrying any of the given HA labels."""
        entity_registry = er.async_get(self.hass)
        wanted = set(labels)
        automation_ids: set[str] = set()

        for entity_entry in entity_registry.entities.values():
            if entity_entry.domain != "automation":
                continue
            if wanted & set(entity_entry.labels):
                automation_ids.add(entity_entry.entity_id)

        return sorted(automation_ids)

    async def _async_trigger_automation(
        self, interaction: discord.Interaction, automation_id: str
    ) -> None:
        """Trigger a Home Assistant automation from a slash command."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        state = self.hass.states.get(automation_id)
        if state is None:
            await interaction.followup.send(
                f"❌ Automatisation `{automation_id}` introuvable.",
                ephemeral=True,
            )
            return

        try:
            await self.hass.services.async_call(
                "automation",
                "trigger",
                {"entity_id": automation_id},
                blocking=True,
            )
            await interaction.followup.send(
                f"✅ Automatisation `{automation_id}` déclenchée."
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Failed to trigger automation %s", automation_id)
            await interaction.followup.send(
                f"❌ Erreur lors du déclenchement de `{automation_id}` : {err}",
                ephemeral=True,
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

        try:
            tpl = Template(format_str, self.hass)
            rendered = tpl.async_render(
                {
                    "state": state.state,
                    "attributes": dict(state.attributes),
                    "entity_id": entity_id,
                    "entity": state,
                }
            )
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

    for bot_config in config.get(DOMAIN, {}).get(CONF_BOTS, []):
        # YAML bots are imported into the config flow (one entry per bot).
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=bot_config,
            )
        )

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
    await manager.async_start()

    # Load the sensor platform for dashboard
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry (disconnect the bot cleanly)."""
    manager: HADiscordBotManager | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if manager:
        await manager.async_stop()
    
    # Unload sensor platform
    await hass.config_entries.async_forward_entry_unload(entry, Platform.SENSOR)
    
    return True
