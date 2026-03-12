"""Pipeline event interceptor for assist_satellite entities.

Patches the on_pipeline_event method of a specific satellite entity instance
to capture TTS events and play them on a configured media player.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.network import get_url

from .const import (
    STATE_ERROR,
    STATE_IDLE,
    STATE_LISTENING,
    STATE_PROCESSING,
    STATE_RESPONDING,
)

_LOGGER = logging.getLogger(__name__)


class PipelineInterceptor:
    """Intercept pipeline events from a satellite and play TTS on a media player.

    Works by patching the on_pipeline_event method on the target satellite
    entity instance. This is non-invasive: it only affects the single entity,
    does not modify any global functions, and is fully reversible on unload.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        satellite_entity_id: str,
        media_player_entity_id: str,
    ) -> None:
        """Initialize the interceptor."""
        self.hass = hass
        self._satellite_entity_id = satellite_entity_id
        self._media_player_entity_id = media_player_entity_id
        self._satellite_entity: Any = None
        self._original_on_pipeline_event: Any = None
        self._active = False

        # State tracking
        self._state = STATE_IDLE
        self._state_listeners: list = []
        self._last_text: str | None = None
        self._last_response: str | None = None

    # -- Public properties --

    @property
    def state(self) -> str:
        """Return current pipeline state."""
        return self._state

    @property
    def last_text(self) -> str | None:
        """Return last recognized speech text."""
        return self._last_text

    @property
    def last_response(self) -> str | None:
        """Return last assistant response text."""
        return self._last_response

    @property
    def satellite_entity_id(self) -> str:
        """Return the monitored satellite entity ID."""
        return self._satellite_entity_id

    @property
    def media_player_entity_id(self) -> str:
        """Return the target media player entity ID."""
        return self._media_player_entity_id

    @property
    def is_active(self) -> bool:
        """Return True if the interceptor is patched and active."""
        return self._active

    # -- State management --

    def add_state_listener(self, listener) -> None:
        """Add a callback for state changes."""
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener) -> None:
        """Remove a state change callback."""
        if listener in self._state_listeners:
            self._state_listeners.remove(listener)

    def _set_state(self, state: str) -> None:
        """Update state and notify listeners."""
        self._state = state
        for listener in self._state_listeners:
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error in state listener", exc_info=True)

    # -- Lifecycle --

    async def async_start(self) -> bool:
        """Find the satellite entity and patch its on_pipeline_event.

        Returns True if patching succeeded, False otherwise.
        """
        entity = self._find_satellite_entity()

        if entity is None:
            _LOGGER.error(
                "Could not find satellite entity '%s'. "
                "Make sure the entity is available and the integration is loaded",
                self._satellite_entity_id,
            )
            return False

        self._satellite_entity = entity
        self._original_on_pipeline_event = entity.on_pipeline_event

        # Replace on_pipeline_event on the instance (not the class)
        entity.on_pipeline_event = self._intercepted_on_pipeline_event

        self._active = True
        _LOGGER.info(
            "Interceptor active: %s → %s",
            self._satellite_entity_id,
            self._media_player_entity_id,
        )
        return True

    async def async_stop(self) -> None:
        """Restore the original on_pipeline_event and clean up."""
        if self._satellite_entity and self._original_on_pipeline_event:
            self._satellite_entity.on_pipeline_event = (
                self._original_on_pipeline_event
            )
            _LOGGER.info(
                "Interceptor removed from %s", self._satellite_entity_id
            )

        self._satellite_entity = None
        self._original_on_pipeline_event = None
        self._active = False
        self._state_listeners.clear()

    # -- Entity lookup --

    def _find_satellite_entity(self) -> Any:
        """Find the satellite entity object via entity platforms."""
        platforms = async_get_platforms(self.hass, "assist_satellite")
        for platform in platforms:
            for entity in platform.entities.values():
                if entity.entity_id == self._satellite_entity_id:
                    return entity
        return None

    # -- Pipeline event handling --

    @callback
    def _intercepted_on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events: track state and capture TTS for media player."""
        try:
            self._process_event(event)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error processing pipeline event")

        # Always forward the event to the original satellite handler
        if self._original_on_pipeline_event:
            self._original_on_pipeline_event(event)

    @callback
    def _process_event(self, event: PipelineEvent) -> None:
        """Extract data from pipeline events and trigger TTS playback."""
        event_type = event.type
        data = event.data or {}

        if event_type == PipelineEventType.STT_START:
            self._set_state(STATE_LISTENING)

        elif event_type == PipelineEventType.STT_END:
            self._set_state(STATE_PROCESSING)
            stt_output = data.get("stt_output", {})
            self._last_text = stt_output.get("text")
            if self._last_text:
                _LOGGER.debug("Recognized: %s", self._last_text)

        elif event_type == PipelineEventType.INTENT_END:
            intent_output = data.get("intent_output", {})
            response = intent_output.get("response", {})
            speech = response.get("speech", {})
            plain = speech.get("plain", {})
            self._last_response = plain.get("speech", "")

        elif event_type == PipelineEventType.TTS_END:
            self._set_state(STATE_RESPONDING)
            tts_output = data.get("tts_output", {})
            tts_url = tts_output.get("url")
            if tts_url:
                _LOGGER.debug("TTS URL captured: %s", tts_url)
                self.hass.async_create_task(
                    self._play_tts_on_media_player(tts_url)
                )

        elif event_type == PipelineEventType.RUN_END:
            self._set_state(STATE_IDLE)

        elif event_type == PipelineEventType.ERROR:
            _LOGGER.error(
                "Pipeline error: %s - %s",
                data.get("code", "unknown"),
                data.get("message", ""),
            )
            self._set_state(STATE_ERROR)

    # -- TTS playback --

    async def _play_tts_on_media_player(self, tts_url: str) -> None:
        """Play TTS audio on the configured media player."""
        # Make URL absolute if it's a relative path
        if tts_url.startswith("/"):
            try:
                base_url = get_url(self.hass)
                tts_url = f"{base_url}{tts_url}"
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not determine HA base URL, using relative URL"
                )

        _LOGGER.debug(
            "Playing TTS on %s: %s",
            self._media_player_entity_id,
            tts_url,
        )

        try:
            await self.hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": self._media_player_entity_id,
                    "media_content_id": tts_url,
                    "media_content_type": "music",
                },
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to play TTS on %s", self._media_player_entity_id
            )
