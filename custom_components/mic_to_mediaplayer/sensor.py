"""Sensor entity for voice pipeline state tracking."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    STATE_ERROR,
    STATE_IDLE,
    STATE_LISTENING,
    STATE_PROCESSING,
    STATE_RESPONDING,
)
from .interceptor import PipelineInterceptor

STATE_LABELS = {
    STATE_IDLE: "Bereit",
    STATE_LISTENING: "Höre zu...",
    STATE_PROCESSING: "Verarbeite...",
    STATE_RESPONDING: "Antwort wird abgespielt",
    STATE_ERROR: "Fehler",
}

STATE_ICONS = {
    STATE_IDLE: "mdi:microphone-off",
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
    interceptor: PipelineInterceptor = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PipelineStateSensor(entry, interceptor)])


class PipelineStateSensor(SensorEntity):
    """Sensor that shows the current voice pipeline state."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, interceptor: PipelineInterceptor) -> None:
        """Initialize the sensor."""
        self._interceptor = interceptor
        self._attr_unique_id = f"{entry.entry_id}_state"
        self._attr_name = "Pipeline Status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Mic to MediaPlayer",
            "model": "Voice Pipeline Interceptor",
        }

    @property
    def native_value(self) -> str:
        """Return the current state."""
        return STATE_LABELS.get(self._interceptor.state, self._interceptor.state)

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        return STATE_ICONS.get(self._interceptor.state, "mdi:microphone-off")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        attrs: dict = {
            "pipeline_state": self._interceptor.state,
            "satellite_entity": self._interceptor.satellite_entity_id,
            "media_player_entity": self._interceptor.media_player_entity_id,
            "pipeline_id": self._interceptor.pipeline_id,
            "interceptor_active": self._interceptor.is_active,
            "alexa_tts_mode": self._interceptor.is_alexa,
        }
        if self._interceptor.last_text:
            attrs["last_speech_text"] = self._interceptor.last_text
        if self._interceptor.last_response:
            attrs["last_response"] = self._interceptor.last_response
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register state listener when added to HA."""
        self._interceptor.add_state_listener(self._handle_state_change)

    async def async_will_remove_from_hass(self) -> None:
        """Remove state listener when removed from HA."""
        self._interceptor.remove_state_listener(self._handle_state_change)

    @callback
    def _handle_state_change(self) -> None:
        """Handle pipeline state changes."""
        self.async_write_ha_state()
