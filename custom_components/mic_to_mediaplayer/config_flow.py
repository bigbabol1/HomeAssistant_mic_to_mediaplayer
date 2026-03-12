"""Config flow for Mic to MediaPlayer integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_MEDIA_PLAYER,
    CONF_SATELLITE_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MicToMediaPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mic to MediaPlayer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            satellite_id = user_input[CONF_SATELLITE_ENTITY]
            media_player_id = user_input[CONF_MEDIA_PLAYER]

            # Validate that the satellite entity exists
            state = self.hass.states.get(satellite_id)
            if state is None:
                errors["base"] = "satellite_not_found"
            else:
                # Create a readable title
                satellite_name = state.attributes.get("friendly_name", satellite_id)
                mp_state = self.hass.states.get(media_player_id)
                mp_name = (
                    mp_state.attributes.get("friendly_name", media_player_id)
                    if mp_state
                    else media_player_id
                )
                title = f"{satellite_name} → {mp_name}"
                return self.async_create_entry(title=title, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SATELLITE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="assist_satellite")
                ),
                vol.Required(CONF_MEDIA_PLAYER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MicToMediaPlayerOptionsFlow(config_entry)


class MicToMediaPlayerOptionsFlow(OptionsFlow):
    """Handle options flow for Mic to MediaPlayer."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SATELLITE_ENTITY,
                    default=current.get(CONF_SATELLITE_ENTITY, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="assist_satellite")
                ),
                vol.Required(
                    CONF_MEDIA_PLAYER,
                    default=current.get(CONF_MEDIA_PLAYER, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
