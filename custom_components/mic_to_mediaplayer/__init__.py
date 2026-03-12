"""The Mic to MediaPlayer integration.

Intercepts pipeline events from an assist_satellite entity and plays
TTS responses on a selected media player entity.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback

from .const import CONF_MEDIA_PLAYER, CONF_SATELLITE_ENTITY, DOMAIN, PLATFORMS
from .interceptor import PipelineInterceptor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mic to MediaPlayer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    satellite_entity_id = entry.data[CONF_SATELLITE_ENTITY]
    media_player_entity_id = entry.data[CONF_MEDIA_PLAYER]

    interceptor = PipelineInterceptor(
        hass, satellite_entity_id, media_player_entity_id
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
            # Set up a state listener to retry when the entity appears
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
    """Listen for state changes and retry attaching when the satellite appears."""
    satellite_entity_id = entry.data[CONF_SATELLITE_ENTITY]

    @callback
    def _state_changed(event) -> None:
        """Check if the satellite entity has appeared."""
        entity_id = event.data.get("entity_id")
        if entity_id == satellite_entity_id and not interceptor.is_active:
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

    return unload_ok
