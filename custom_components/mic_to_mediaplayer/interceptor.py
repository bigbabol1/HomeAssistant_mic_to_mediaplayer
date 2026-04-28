"""Pipeline event interceptor for assist_satellite entities.

Patches the on_pipeline_event method of a specific satellite entity instance
to capture TTS events and play them on a configured media player.
"""

from __future__ import annotations

import asyncio
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
        self._is_alexa: bool = False

        # State tracking
        self._state = STATE_IDLE
        self._state_listeners: list = []
        self._last_text: str | None = None
        self._last_response: str | None = None
        self._continue_conversation: bool = False

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

    @property
    def is_alexa(self) -> bool:
        """Return True if the media player is an Alexa device."""
        return self._is_alexa

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

        # Detect if media player is from alexa_media integration
        self._is_alexa = self._detect_alexa_media_player()

        _LOGGER.info(
            "Interceptor active: %s → %s%s",
            self._satellite_entity_id,
            self._media_player_entity_id,
            " (Alexa TTS mode)" if self._is_alexa else "",
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

    # -- Media player detection --

    def _detect_alexa_media_player(self) -> bool:
        """Check if the configured media player belongs to alexa_media."""
        entity_reg = er.async_get(self.hass)
        entry = entity_reg.async_get(self._media_player_entity_id)
        if entry is not None and entry.platform == "alexa_media":
            return True
        return False

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
            # Conversation agents set continue_conversation when expecting
            # a follow-up reply without re-triggering the wake word.
            self._continue_conversation = bool(
                intent_output.get("continue_conversation", False)
            )
            if self._continue_conversation:
                _LOGGER.debug("Conversation flagged for follow-up")

        elif event_type == PipelineEventType.TTS_END:
            self._set_state(STATE_RESPONDING)
            if self._is_alexa:
                # Alexa doesn't support direct audio URL streaming.
                # Use notify.alexa_media with the response text instead.
                if self._last_response:
                    _LOGGER.debug(
                        "Alexa TTS via notify: %s", self._last_response
                    )
                    self.hass.async_create_task(
                        self._speak_tts_via_alexa(self._last_response)
                    )
            else:
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

    async def _speak_tts_via_alexa(self, message: str) -> None:
        """Send TTS text to an Alexa device via notify.alexa_media."""
        _LOGGER.debug(
            "Speaking on Alexa %s: %s",
            self._media_player_entity_id,
            message,
        )

        try:
            await self.hass.services.async_call(
                "notify",
                "alexa_media",
                {
                    "target": self._media_player_entity_id,
                    "message": message,
                    "data": {"type": "tts"},
                },
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to speak TTS on Alexa %s",
                self._media_player_entity_id,
            )

    async def _play_tts_on_media_player(self, tts_url: str) -> None:
        """Play TTS audio on the configured media player.

        After playback finishes, signal the satellite that TTS is done so
        the assist_satellite entity can transition out of the responding
        state. Without this signal, the satellite remains stuck at
        "responding" because play_media's blocking=True only waits for the
        service call to return (URL queued), not for actual playback to end.
        """
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
            self._signal_tts_finished()
            return

        await self._wait_for_media_player_idle()
        self._signal_tts_finished()

        continue_flag = self._continue_conversation
        self._continue_conversation = False

        persistent_on = self._persistent_switch_on()

        if persistent_on:
            if continue_flag:
                await self._call_esphome_service("start_follow_up")
            else:
                await self._call_esphome_service("end_persistent")
        elif continue_flag:
            await self._call_esphome_service("start_follow_up")

    async def _wait_for_media_player_idle(
        self, start_grace: float = 0.3, timeout: float = 60.0, poll: float = 0.1
    ) -> None:
        """Wait until the media_player reports an idle/finished state.

        Gives the player a brief grace period to begin playback, then polls
        until it returns to idle/paused/off, or until timeout. Grace and
        poll cadence are kept short so the satellite can re-enter STT for
        a continue_conversation follow-up before the user starts speaking.
        """
        await asyncio.sleep(start_grace)

        elapsed = 0.0
        idle_states = {"idle", "paused", "off", "standby", "unknown", "unavailable"}
        while elapsed < timeout:
            state = self.hass.states.get(self._media_player_entity_id)
            if state is None or state.state in idle_states:
                return
            await asyncio.sleep(poll)
            elapsed += poll

        _LOGGER.debug(
            "Timeout waiting for %s to go idle (still %s)",
            self._media_player_entity_id,
            state.state if state else "<missing>",
        )

    def _signal_tts_finished(self) -> None:
        """Tell the satellite that TTS playback has completed.

        Tries known assist_satellite hooks first, then falls back to firing
        a synthetic RUN_END through the original on_pipeline_event handler.
        """
        entity = self._satellite_entity
        if entity is None:
            return

        for method_name in (
            "tts_response_finished",
            "_internal_on_tts_response_finished",
            "async_on_tts_response_finished",
        ):
            method = getattr(entity, method_name, None)
            if method is None:
                continue
            try:
                result = method()
                if asyncio.iscoroutine(result):
                    self.hass.async_create_task(result)
                _LOGGER.debug(
                    "Signaled TTS finished via %s on %s",
                    method_name,
                    self._satellite_entity_id,
                )
                return
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Calling %s failed; trying next fallback",
                    method_name,
                    exc_info=True,
                )

        # Fallback: synthesize a RUN_END so the satellite's own state machine
        # closes the pipeline. Only the original handler is invoked, since the
        # interceptor itself already saw RUN_END from the real pipeline.
        if self._original_on_pipeline_event:
            try:
                synthetic = PipelineEvent(PipelineEventType.RUN_END, {})
                self._original_on_pipeline_event(synthetic)
                _LOGGER.debug(
                    "Signaled TTS finished via synthetic RUN_END on %s",
                    self._satellite_entity_id,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Synthetic RUN_END dispatch failed", exc_info=True
                )

    def _esphome_device_name(self) -> str | None:
        """Return normalized ESPHome device name for service/entity lookup."""
        entity_reg = er.async_get(self.hass)
        registry_entry = entity_reg.async_get(self._satellite_entity_id)
        if registry_entry is None or registry_entry.platform != "esphome":
            return None

        device_id = registry_entry.device_id
        if device_id is None:
            return None

        from homeassistant.helpers import device_registry as dr

        device = dr.async_get(self.hass).async_get(device_id)
        if device is None:
            return None

        device_name = (device.name_by_user or device.name or "").strip()
        if not device_name:
            return None

        return device_name.lower().replace(" ", "_").replace("-", "_")

    def _persistent_switch_on(self) -> bool:
        """Read state of the satellite's persistent_conversation switch.

        Returns False if switch missing (legacy firmware) — preserves old
        behavior so older satellites keep working unchanged.
        """
        entity_reg = er.async_get(self.hass)
        registry_entry = entity_reg.async_get(self._satellite_entity_id)
        if registry_entry is None or registry_entry.device_id is None:
            return False

        for entry in er.async_entries_for_device(
            entity_reg, registry_entry.device_id
        ):
            if entry.domain != "switch":
                continue
            if "persistent_conversation" not in entry.entity_id:
                continue
            state = self.hass.states.get(entry.entity_id)
            if state is None:
                return False
            return state.state == "on"
        return False

    async def _call_esphome_service(self, service_suffix: str) -> None:
        """Call esphome.<device>_<service_suffix> if registered."""
        device_name = self._esphome_device_name()
        if device_name is None:
            _LOGGER.debug(
                "Skipping esphome service: %s is not an ESPHome satellite",
                self._satellite_entity_id,
            )
            return

        service_name = f"{device_name}_{service_suffix}"

        if not self.hass.services.has_service("esphome", service_name):
            _LOGGER.debug(
                "ESPHome service esphome.%s not found — add it to device YAML",
                service_name,
            )
            return

        try:
            await self.hass.services.async_call(
                "esphome", service_name, {}, blocking=False
            )
            _LOGGER.debug("Triggered esphome.%s", service_name)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to call esphome.%s", service_name)
