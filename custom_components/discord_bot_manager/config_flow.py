"""Config flow for the Discord Bot Manager integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr

from .const import (
    CONF_AUTOMATION_LABELS,
    CONF_COMMAND,
    CONF_DESCRIPTION,
    CONF_ENTITIES,
    CONF_FORMAT,
    CONF_GUILD_ID,
    CONF_LABELS,
    CONF_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _sanitize_labels(raw: str) -> list[str]:
    """Parse comma-separated labels string into list."""
    return [
        label.strip()
        for label in raw.split(",")
        if label.strip()
    ]


class DiscordBotManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord Bot Manager."""

    VERSION = 1

    def _validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user input and return an error dict."""
        errors: dict[str, str] = {}

        if not str(user_input.get(CONF_TOKEN, "") or "").strip():
            errors[CONF_TOKEN] = "missing_token"

        guild_id = str(user_input.get(CONF_GUILD_ID, "") or "").strip()
        if guild_id and not guild_id.isdigit():
            errors[CONF_GUILD_ID] = "invalid_guild_id"

        return errors

    async def _async_get_available_labels(self) -> list[str]:
        """Return list of existing Home Assistant labels."""
        try:
            registry = lr.async_get(self.hass)
            return sorted(registry.labels.keys())
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not fetch label registry", exc_info=True)
            return []

    async def _async_create_label(self, label_name: str) -> bool:
        """Create a new HA label."""
        try:
            registry = lr.async_get(self.hass)
            registry.async_create_label(label_name)
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to create label '%s': %s", label_name, err)
            return False

    async def _async_get_automation_commands(self, labels: list[str]) -> list[dict[str, str]]:
        """Get automation commands from labels."""
        try:
            entity_registry = er.async_get(self.hass)
            commands = []
            for entity_entry in entity_registry.entities.values():
                if entity_entry.domain == "automation":
                    entity_labels = set(entity_entry.labels)
                    if any(label in entity_labels for label in labels):
                        state = self.hass.states.get(entity_entry.entity_id)
                        friendly_name = (
                            state.attributes.get("friendly_name", entity_entry.entity_id)
                            if state
                            else entity_entry.entity_id
                        )
                        commands.append({
                            "entity_id": entity_entry.entity_id,
                            "command": entity_entry.entity_id.split(".", 1)[-1],
                            "description": f"Déclenche l'automatisation '{friendly_name}'",
                            "format": f"✅ Automatisation `{entity_entry.entity_id}` déclenchée.",
                        })
            return commands
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to get automation commands: %s", err)
            return []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial UI step (token / guild / labels)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate(user_input)

            if not errors:
                token = str(user_input[CONF_TOKEN]).strip()
                guild_id = str(user_input.get(CONF_GUILD_ID, "") or "").strip()
                labels_raw = str(user_input.get(CONF_LABELS, "") or "")
                labels = _sanitize_labels(labels_raw)
                new_label = str(user_input.get("_new_label", "") or "").strip()

                # Create new label if provided
                if new_label:
                    await self._async_create_label(new_label)
                    if new_label not in labels:
                        labels.append(new_label)

                # Fetch automation commands based on selected labels
                automation_commands = await self._async_get_automation_commands(labels)

                # One entry per bot token.
                await self.async_set_unique_id(token)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Discord Bot Manager",
                    data={
                        CONF_TOKEN: token,
                        CONF_GUILD_ID: guild_id,
                        CONF_LABELS: labels,
                        CONF_AUTOMATION_LABELS: labels,
                        CONF_ENTITIES: automation_commands,
                    },
                )

        # Fetch available labels for the dropdown
        available_labels = await self._async_get_available_labels()

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_GUILD_ID, default=""): cv.string,
                vol.Optional(CONF_LABELS, default=""): cv.string,
                vol.Optional("_new_label", default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "available_labels": ", ".join(available_labels) or "Aucune étiquette configurée",
                "help_url": "https://git.home-deneuville.fr/Edern/homeassistant-discord-bot-manager",
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of an existing bot."""
        entry: ConfigEntry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        current_token = str(entry.data.get(CONF_TOKEN, "") or "")
        current_guild_id = str(entry.data.get(CONF_GUILD_ID, "") or "")
        current_labels = entry.data.get(CONF_LABELS, [])
        current_entities = entry.data.get(CONF_ENTITIES, [])

        if user_input is not None:
            errors = self._validate(user_input)

            if not errors:
                token = str(user_input[CONF_TOKEN]).strip()
                guild_id = str(user_input.get(CONF_GUILD_ID, "") or "").strip()
                labels_raw = str(user_input.get(CONF_LABELS, "") or "")
                labels = _sanitize_labels(labels_raw)
                new_label = str(user_input.get("_new_label", "") or "").strip()

                # Create new label if provided
                if new_label:
                    await self._async_create_label(new_label)
                    if new_label not in labels:
                        labels.append(new_label)

                # Re-fetch automation commands based on updated labels
                automation_commands = await self._async_get_automation_commands(labels)

                # Update entry data
                updated_data = {
                    **entry.data,
                    CONF_TOKEN: token,
                    CONF_GUILD_ID: guild_id,
                    CONF_LABELS: labels,
                    CONF_AUTOMATION_LABELS: labels,
                    CONF_ENTITIES: automation_commands,
                }

                self.hass.config_entries.async_update_entry(
                    entry,
                    data=updated_data,
                )

                # Restart the bot with new configuration
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reconfigured")

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN, default=current_token): str,
                vol.Optional(CONF_GUILD_ID, default=current_guild_id): cv.string,
                vol.Optional(CONF_LABELS, default=", ".join(current_labels)): cv.string,
                vol.Optional("_new_label", default=""): str,
            }
        )

        available_labels = await self._async_get_available_labels()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "available_labels": ", ".join(available_labels) or "Aucune étiquette configurée",
            },
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        token = str(import_config.get(CONF_TOKEN, "") or "").strip()

        if not token:
            _LOGGER.warning("Skipping Discord bot entry without token")
            return self.async_abort(reason="missing_token")

        await self.async_set_unique_id(token)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Discord Bot (YAML)",
            data={
                CONF_TOKEN: token,
                CONF_GUILD_ID: str(
                    import_config.get(CONF_GUILD_ID, "") or ""
                ).strip(),
                CONF_LABELS: list(import_config.get(CONF_LABELS, []) or []),
                CONF_AUTOMATION_LABELS: list(
                    import_config.get(CONF_AUTOMATION_LABELS)
                    or import_config.get(CONF_LABELS)
                    or []
                ),
                CONF_ENTITIES: list(import_config.get(CONF_ENTITIES, []) or []),
            },
        )
