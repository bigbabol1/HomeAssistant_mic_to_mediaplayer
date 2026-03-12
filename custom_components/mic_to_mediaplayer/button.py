"""Button entity for triggering voice pipeline listening."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the listen button."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ListenButton(entry, manager)])


class ListenButton(ButtonEntity):
    """Button to start voice pipeline listening."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:microphone"

    def __init__(self, entry: ConfigEntry, manager) -> None:
        """Initialize the button."""
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_listen"
        self._attr_name = "Zuhören starten"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Mic to MediaPlayer",
            "model": "Voice Pipeline",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        if self._manager.is_running:
            _LOGGER.warning("Voice pipeline is already running")
            return
        self.hass.async_create_task(self._manager.run())
