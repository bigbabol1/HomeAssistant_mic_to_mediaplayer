"""The Mic to MediaPlayer integration.

Intercepts pipeline events from an assist_satellite entity and plays
TTS responses on a selected media player entity.
"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MEDIA_PLAYER,
    CONF_PIPELINE_ID,
    CONF_SATELLITE_ENTITY,
    DOMAIN,
    PLATFORMS,
)
from .interceptor import PipelineInterceptor

_LOGGER = logging.getLogger(__name__)

SERVICE_ANNOUNCE = "announce"
ANNOUNCE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional("satellite_entity_id"): cv.entity_id,
            vol.Optional("message"): cv.string,
            vol.Optional("audio_url"): cv.string,
            vol.Optional("tts_entity_id"): cv.entity_id,
            vol.Optional("language"): cv.string,
        },
        cv.has_at_least_one_key("message", "audio_url"),
    )
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mic to MediaPlayer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register the announce service once, on first config entry setup.
    if not hass.services.has_service(DOMAIN, SERVICE_ANNOUNCE):
        async def _handle_announce(call: ServiceCall) -> None:
            satellite_id = call.data.get("satellite_entity_id")
            interceptors: list[PipelineInterceptor] = list(
                hass.data.get(DOMAIN, {}).values()
            )
            if not interceptors:
                _LOGGER.warning("announce called but no Mic2MP instances are active")
                return

            target: PipelineInterceptor | None = None
            if satellite_id:
                for ic in interceptors:
                    if ic.satellite_entity_id == satellite_id:
                        target = ic
                        break
                if target is None:
                    _LOGGER.warning(
                        "announce: no Mic2MP instance is bound to satellite %s "
                        "(known: %s)",
                        satellite_id,
                        [ic.satellite_entity_id for ic in interceptors],
                    )
                    return
            else:
                if len(interceptors) > 1:
                    _LOGGER.warning(
                        "announce called without satellite_entity_id but %d "
                        "Mic2MP instances exist; using the first (%s)",
                        len(interceptors),
                        interceptors[0].satellite_entity_id,
                    )
                target = interceptors[0]

            await target.async_play_announcement(
                message=call.data.get("message"),
                audio_url=call.data.get("audio_url"),
                tts_entity_id=call.data.get("tts_entity_id"),
                language=call.data.get("language"),
            )

        hass.services.async_register(
            DOMAIN, SERVICE_ANNOUNCE, _handle_announce, schema=ANNOUNCE_SCHEMA
        )

    satellite_entity_id = entry.data[CONF_SATELLITE_ENTITY]
    media_player_entity_id = entry.data[CONF_MEDIA_PLAYER]
    pipeline_id = entry.data.get(CONF_PIPELINE_ID)

    interceptor = PipelineInterceptor(
        hass, satellite_entity_id, media_player_entity_id, pipeline_id
    )
    hass.data[DOMAIN][entry.entry_id] = interceptor

    # Forward setup to platforms (sensor) before starting the interceptor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The satellite entity may not be available yet during HA startup.
    # Defer interceptor activation until HA is fully started.
    async def _start_interceptor(_event=None) -> None:
        """Activate the interceptor once all entities are available."""
        success = await interceptor.async_start()
        if not success:
            _LOGGER.warning(
                "Could not attach to satellite '%s'. "
                "Will retry when the entity becomes available",
                satellite_entity_id,
            )
            _setup_retry_listener(hass, entry, interceptor)

    if hass.is_running:
        await _start_interceptor()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start_interceptor)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


@callback
def _setup_retry_listener(
    hass: HomeAssistant, entry: ConfigEntry, interceptor: PipelineInterceptor
) -> None:
    """Listen for the specific satellite entity to appear and retry attaching."""
    satellite_entity_id = entry.data[CONF_SATELLITE_ENTITY]
    retry_logged = False

    @callback
    def _state_changed(event) -> None:
        """Retry attaching when the target satellite entity fires a state change."""
        nonlocal retry_logged
        entity_id = event.data.get("entity_id")
        if entity_id != satellite_entity_id or interceptor.is_active:
            return

        if not retry_logged:
            _LOGGER.debug(
                "Satellite '%s' state changed, attempting to attach",
                satellite_entity_id,
            )
            retry_logged = True

        hass.async_create_task(_try_attach())

    async def _try_attach() -> None:
        success = await interceptor.async_start()
        if success:
            unsub()

    unsub = hass.bus.async_listen("state_changed", _state_changed)
    entry.async_on_unload(unsub)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    interceptor: PipelineInterceptor | None = hass.data[DOMAIN].get(entry.entry_id)

    if interceptor:
        await interceptor.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_ANNOUNCE):
            hass.services.async_remove(DOMAIN, SERVICE_ANNOUNCE)

    return unload_ok
