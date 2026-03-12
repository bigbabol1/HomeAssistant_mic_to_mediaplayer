"""The Mic to MediaPlayer integration.

Connects a Wyoming Protocol microphone to Home Assistant's assist pipeline
and plays TTS responses on a selected media player entity.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS
from .pipeline import VoicePipelineManager

_LOGGER = logging.getLogger(__name__)

type MicToMediaPlayerConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: MicToMediaPlayerConfigEntry) -> bool:
    """Set up Mic to MediaPlayer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create the pipeline manager
    manager = VoicePipelineManager(hass, dict(entry.data))
    hass.data[DOMAIN][entry.entry_id] = manager

    # Register a service to trigger listening
    async def handle_listen(call: ServiceCall) -> None:
        """Handle the listen service call."""
        entry_id = call.data.get("entry_id")
        if entry_id and entry_id in hass.data[DOMAIN]:
            mgr = hass.data[DOMAIN][entry_id]
        elif len(hass.data[DOMAIN]) == 1:
            # If only one entry, use it
            mgr = next(iter(hass.data[DOMAIN].values()))
        else:
            _LOGGER.error("Please specify entry_id when multiple instances are configured")
            return
        await mgr.run()

    if not hass.services.has_service(DOMAIN, "listen"):
        hass.services.async_register(DOMAIN, "listen", handle_listen)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    # Remove service if no more entries
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "listen")

    return unload_ok
