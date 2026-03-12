"""Sensor entity for voice pipeline state tracking."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    STATE_CONNECTING,
    STATE_ERROR,
    STATE_IDLE,
    STATE_LISTENING,
    STATE_PROCESSING,
    STATE_RESPONDING,
)


STATE_LABELS = {
    STATE_IDLE: "Bereit",
    STATE_CONNECTING: "Verbinde...",
    STATE_LISTENING: "Höre zu...",
    STATE_PROCESSING: "Verarbeite...",
    STATE_RESPONDING: "Antwort wird abgespielt",
    STATE_ERROR: "Fehler",
}

STATE_ICONS = {
    STATE_IDLE: "mdi:microphone-off",
    STATE_CONNECTING: "mdi:connection",
    STATE_LISTENING: "mdi:microphone",
    STATE_PROCESSING: "mdi:brain",
    STATE_RESPONDING: "mdi:speaker",
    STATE_ERROR: "mdi:alert-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pipeline state sensor."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PipelineStateSensor(entry, manager)])


class PipelineStateSensor(SensorEntity):
    """Sensor that shows the current voice pipeline state."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_state"
        self._attr_name = "Pipeline Status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Mic to MediaPlayer",
            "model": "Voice Pipeline",
        }

    @property
    def native_value(self) -> str:
        """Return the current state."""
        return STATE_LABELS.get(self._manager.state, self._manager.state)

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        return STATE_ICONS.get(self._manager.state, "mdi:microphone-off")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        attrs = {"pipeline_state": self._manager.state}
        if self._manager.last_text:
            attrs["last_speech_text"] = self._manager.last_text
        if self._manager.last_response:
            attrs["last_response"] = self._manager.last_response
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register state listener when added to HA."""
        self._manager.add_state_listener(self._handle_state_change)

    async def async_will_remove_from_hass(self) -> None:
        """Remove state listener when removed from HA."""
        self._manager.remove_state_listener(self._handle_state_change)

    @callback
    def _handle_state_change(self) -> None:
        """Handle pipeline state changes."""
        self.async_write_ha_state()
