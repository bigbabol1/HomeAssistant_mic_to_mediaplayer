"""Config flow for Mic to MediaPlayer integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_LANGUAGE,
    CONF_MEDIA_PLAYER,
    CONF_PIPELINE_ID,
    CONF_SILENCE_SECONDS,
    CONF_WYOMING_HOST,
    CONF_WYOMING_PORT,
    DEFAULT_PORT,
    DEFAULT_SILENCE_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _test_wyoming_connection(host: str, port: int) -> bool:
    """Test if Wyoming service is reachable."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _get_pipeline_options(hass) -> list[selector.SelectOptionDict]:
    """Get available assist pipelines as select options."""
    options: list[selector.SelectOptionDict] = [
        selector.SelectOptionDict(value="preferred", label="Standard-Pipeline"),
    ]
    try:
        from homeassistant.components.assist_pipeline import async_get_pipelines

        pipelines = async_get_pipelines(hass)
        for pipeline in pipelines:
            options.append(
                selector.SelectOptionDict(value=pipeline.id, label=pipeline.name)
            )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not load assist pipelines")
    return options


class MicToMediaPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mic to MediaPlayer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Test Wyoming connection
            if not await _test_wyoming_connection(
                user_input[CONF_WYOMING_HOST], user_input[CONF_WYOMING_PORT]
            ):
                errors["base"] = "cannot_connect"
            else:
                # Normalize pipeline_id
                if user_input.get(CONF_PIPELINE_ID) == "preferred":
                    user_input[CONF_PIPELINE_ID] = None

                title = (
                    f"Mic ({user_input[CONF_WYOMING_HOST]}:"
                    f"{user_input[CONF_WYOMING_PORT]}) → "
                    f"{user_input[CONF_MEDIA_PLAYER]}"
                )
                return self.async_create_entry(title=title, data=user_input)

        pipeline_options = _get_pipeline_options(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_WYOMING_HOST): str,
                vol.Required(CONF_WYOMING_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_MEDIA_PLAYER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
                vol.Optional(
                    CONF_PIPELINE_ID, default="preferred"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pipeline_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_LANGUAGE, default=""): str,
                vol.Optional(
                    CONF_SILENCE_SECONDS, default=DEFAULT_SILENCE_SECONDS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0, max=10.0, step=0.5, mode=selector.NumberSelectorMode.SLIDER
                    )
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
            if user_input.get(CONF_PIPELINE_ID) == "preferred":
                user_input[CONF_PIPELINE_ID] = None
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data
        pipeline_options = _get_pipeline_options(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MEDIA_PLAYER,
                    default=current.get(CONF_MEDIA_PLAYER, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
                vol.Optional(
                    CONF_PIPELINE_ID,
                    default=current.get(CONF_PIPELINE_ID) or "preferred",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pipeline_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_LANGUAGE,
                    default=current.get(CONF_LANGUAGE, ""),
                ): str,
                vol.Optional(
                    CONF_SILENCE_SECONDS,
                    default=current.get(CONF_SILENCE_SECONDS, DEFAULT_SILENCE_SECONDS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0, max=10.0, step=0.5, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
