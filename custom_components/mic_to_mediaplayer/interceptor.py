"""Pipeline event interceptor for assist_satellite entities.

Patches the on_pipeline_event method of a specific satellite entity instance
to capture TTS events and play them on a configured media player.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
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
        pipeline_id: str | None = None,
    ) -> None:
        """Initialize the interceptor."""
        self.hass = hass
        self._satellite_entity_id = satellite_entity_id
        self._media_player_entity_id = media_player_entity_id
        self._pipeline_id = pipeline_id
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
    def pipeline_id(self) -> str | None:
        """Return the configured pipeline ID."""
        return self._pipeline_id

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
            _LOGGER.debug(
                "Satellite entity '%s' not found yet",
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

        # Apply pipeline preference to the satellite
        if self._pipeline_id:
            await self._apply_pipeline_preference()

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
        """Find the satellite entity object.

        Uses the entity registry to determine which integration provides the
        satellite, then searches that integration's entity platforms.
        """
        entity_id = self._satellite_entity_id

        # Strategy 1: Use entity registry to find the owning integration,
        # then look up the entity object in that integration's platforms.
        entity_reg = er.async_get(self.hass)
        registry_entry = entity_reg.async_get(entity_id)

        if registry_entry is not None:
            integration = registry_entry.platform  # e.g. "wyoming", "esphome"
            platforms = async_get_platforms(self.hass, integration)
            for platform in platforms:
                if platform.domain == "assist_satellite":
                    entity = platform.entities.get(entity_id)
                    if entity is not None:
                        _LOGGER.debug(
                            "Found satellite via integration '%s'", integration
                        )
                        return entity

        # Strategy 2: Brute-force search across all known satellite providers.
        for integration in ("wyoming", "esphome", "voip", "homeassistant"):
            try:
                platforms = async_get_platforms(self.hass, integration)
            except Exception:  # noqa: BLE001
                continue
            for platform in platforms:
                if platform.domain == "assist_satellite":
                    entity = platform.entities.get(entity_id)
                    if entity is not None:
                        _LOGGER.debug(
                            "Found satellite via fallback search '%s'",
                            integration,
                        )
                        return entity

        return None

    # -- Pipeline preference --

    async def _apply_pipeline_preference(self) -> None:
        """Set the satellite's pipeline select entity to the configured pipeline."""
        try:
            from homeassistant.components.assist_pipeline import async_get_pipeline

            pipeline = async_get_pipeline(self.hass, self._pipeline_id)
            if pipeline is None:
                _LOGGER.warning("Pipeline '%s' not found", self._pipeline_id)
                return

            pipeline_name = pipeline.name
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not resolve pipeline name", exc_info=True)
            return

        # Find the satellite device's pipeline select entity
        pipeline_select_id = self._find_pipeline_select_entity()
        if pipeline_select_id is None:
            _LOGGER.debug(
                "No pipeline select entity found for satellite device"
            )
            return

        # Read current options from the select entity
        select_state = self.hass.states.get(pipeline_select_id)
        if select_state is None:
            return

        options = select_state.attributes.get("options", [])

        # Find the matching option (pipeline name or "preferred")
        target_option = None
        for option in options:
            if option.lower() == pipeline_name.lower():
                target_option = option
                break

        if target_option is None:
            _LOGGER.warning(
                "Pipeline '%s' not found in select options %s",
                pipeline_name,
                options,
            )
            return

        try:
            await self.hass.services.async_call(
                "select",
                "select_option",
                {
                    "entity_id": pipeline_select_id,
                    "option": target_option,
                },
                blocking=True,
            )
            _LOGGER.info(
                "Set satellite pipeline to '%s' via %s",
                target_option,
                pipeline_select_id,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Could not set pipeline on %s", pipeline_select_id
            )

    def _find_pipeline_select_entity(self) -> str | None:
        """Find the pipeline select entity belonging to the satellite's device."""
        entity_reg = er.async_get(self.hass)
        satellite_entry = entity_reg.async_get(self._satellite_entity_id)

        if satellite_entry is None or satellite_entry.device_id is None:
            return None

        # Find all entities for the satellite's device
        device_entities = er.async_entries_for_device(
            entity_reg, satellite_entry.device_id
        )

        for entry in device_entities:
            if entry.domain == "select" and "pipeline" in (
                entry.original_name or entry.entity_id
            ).lower():
                return entry.entity_id

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
