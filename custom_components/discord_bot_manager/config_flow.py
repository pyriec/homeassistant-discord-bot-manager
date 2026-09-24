"""Config flow for the Discord Bot Manager integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTOMATION_LABELS,
    CONF_ENTITIES,
    CONF_GUILD_ID,
    CONF_LABELS,
    CONF_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_GUILD_ID, default=""): cv.string,
        vol.Optional(CONF_LABELS, default=""): cv.string,
    }
)


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial UI step (token / guild / labels)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate(user_input)

            if not errors:
                token = str(user_input[CONF_TOKEN]).strip()
                labels_raw = str(user_input.get(CONF_LABELS, "") or "")
                labels = [
                    label.strip()
                    for label in labels_raw.split(",")
                    if label.strip()
                ]

                # One entry per bot token.
                await self.async_set_unique_id(token)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Discord Bot Manager",
                    data={
                        CONF_TOKEN: token,
                        CONF_GUILD_ID: str(
                            user_input.get(CONF_GUILD_ID, "") or ""
                        ).strip(),
                        CONF_LABELS: labels,
                        CONF_AUTOMATION_LABELS: labels,
                        CONF_ENTITIES: [],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
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