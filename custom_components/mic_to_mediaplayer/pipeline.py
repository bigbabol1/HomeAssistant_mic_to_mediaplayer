"""Core voice pipeline logic: Wyoming mic -> Assist Pipeline -> MediaPlayer."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from wyoming.audio import AudioChunk, AudioStop
from wyoming.event import async_read_event, async_write_event
from wyoming.info import Describe, Info

from homeassistant.components.assist_pipeline import (
    AudioSettings,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    async_pipeline_from_audio_stream,
)
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.network import get_url

from .const import (
    CONF_LANGUAGE,
    CONF_MEDIA_PLAYER,
    CONF_PIPELINE_ID,
    CONF_SILENCE_SECONDS,
    CONF_WYOMING_HOST,
    CONF_WYOMING_PORT,
    DEFAULT_SILENCE_SECONDS,
    STATE_CONNECTING,
    STATE_ERROR,
    STATE_IDLE,
    STATE_LISTENING,
    STATE_PROCESSING,
    STATE_RESPONDING,
)

_LOGGER = logging.getLogger(__name__)

# Wyoming audio defaults
WYOMING_SAMPLE_RATE = 16000
WYOMING_SAMPLE_WIDTH = 2
WYOMING_CHANNELS = 1

# Timeout for reading events from Wyoming (seconds)
WYOMING_READ_TIMEOUT = 30.0


class VoicePipelineManager:
    """Manage the voice pipeline: Wyoming -> Assist Pipeline -> MediaPlayer."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the pipeline manager."""
        self.hass = hass
        self._config = config
        self._state = STATE_IDLE
        self._state_listeners: list = []
        self._running = False
        self._last_text: str | None = None
        self._last_response: str | None = None

    @property
    def state(self) -> str:
        """Return current pipeline state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Return True if pipeline is currently running."""
        return self._running

    @property
    def last_text(self) -> str | None:
        """Return last recognized speech text."""
        return self._last_text

    @property
    def last_response(self) -> str | None:
        """Return last assistant response text."""
        return self._last_response

    def add_state_listener(self, callback) -> None:
        """Add a callback for state changes."""
        self._state_listeners.append(callback)

    def remove_state_listener(self, callback) -> None:
        """Remove a state change callback."""
        self._state_listeners.remove(callback)

    def _set_state(self, state: str) -> None:
        """Update state and notify listeners."""
        self._state = state
        for listener in self._state_listeners:
            listener()

    async def run(self) -> None:
        """Run the full voice pipeline."""
        if self._running:
            _LOGGER.warning("Pipeline is already running")
            return

        self._running = True
        self._last_text = None
        self._last_response = None

        try:
            await self._execute_pipeline()
        except Exception:
            _LOGGER.exception("Voice pipeline error")
            self._set_state(STATE_ERROR)
        finally:
            self._running = False
            # Return to idle after a short delay (so error state is visible)
            if self._state == STATE_ERROR:
                await asyncio.sleep(3)
            self._set_state(STATE_IDLE)

    async def _execute_pipeline(self) -> None:
        """Connect to Wyoming, run assist pipeline, play TTS."""
        host = self._config[CONF_WYOMING_HOST]
        port = self._config[CONF_WYOMING_PORT]
        silence_seconds = self._config.get(CONF_SILENCE_SECONDS, DEFAULT_SILENCE_SECONDS)

        # Step 1: Connect to Wyoming service
        self._set_state(STATE_CONNECTING)
        _LOGGER.debug("Connecting to Wyoming service at %s:%s", host, port)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
        except (OSError, asyncio.TimeoutError) as err:
            _LOGGER.error("Cannot connect to Wyoming service at %s:%s: %s", host, port, err)
            self._set_state(STATE_ERROR)
            return

        try:
            # Step 2: Describe service and prepare connection
            await self._prepare_wyoming_connection(reader, writer)

            # Step 3: Run assist pipeline with Wyoming audio stream
            self._set_state(STATE_LISTENING)
            tts_url = await self._run_assist_pipeline(reader, silence_seconds)

            # Step 4: Play TTS on media player
            if tts_url:
                self._set_state(STATE_RESPONDING)
                await self._play_tts(tts_url)
            else:
                _LOGGER.warning("No TTS output received from pipeline")

        finally:
            writer.close()
            await writer.wait_closed()

    async def _prepare_wyoming_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Send describe and optionally start satellite."""
        try:
            await async_write_event(Describe().event(), writer)
            event = await asyncio.wait_for(
                async_read_event(reader), timeout=5.0
            )

            if event is not None and Info.is_type(event.type):
                info = Info.from_event(event)
                _LOGGER.debug("Wyoming service info: %s", info)

                # If it's a satellite, try to send RunSatellite
                if info.satellite:
                    try:
                        from wyoming.satellite import RunSatellite

                        await async_write_event(RunSatellite().event(), writer)
                        _LOGGER.debug("Sent RunSatellite command")
                    except ImportError:
                        _LOGGER.debug("RunSatellite not available in wyoming package")
        except (asyncio.TimeoutError, OSError):
            _LOGGER.debug("Could not describe Wyoming service, proceeding anyway")

    async def _run_assist_pipeline(
        self, reader: asyncio.StreamReader, silence_seconds: float
    ) -> str | None:
        """Run the HA assist pipeline with audio from Wyoming and return TTS URL."""
        tts_url: str | None = None
        pipeline_id = self._config.get(CONF_PIPELINE_ID)
        language = self._config.get(CONF_LANGUAGE) or ""

        def event_callback(event: PipelineEvent) -> None:
            """Handle pipeline events."""
            nonlocal tts_url

            if event.type == PipelineEventType.STT_START:
                self._set_state(STATE_LISTENING)
            elif event.type == PipelineEventType.STT_END:
                self._set_state(STATE_PROCESSING)
                stt_output = event.data or {}
                self._last_text = stt_output.get("stt_output", {}).get("text")
                if self._last_text:
                    _LOGGER.debug("Recognized speech: %s", self._last_text)
            elif event.type == PipelineEventType.INTENT_END:
                intent_output = event.data or {}
                response = intent_output.get("intent_output", {})
                conversation_response = response.get("response", {})
                speech = conversation_response.get("speech", {})
                plain = speech.get("plain", {})
                self._last_response = plain.get("speech", "")
            elif event.type == PipelineEventType.TTS_END:
                tts_output = (event.data or {}).get("tts_output", {})
                tts_url = tts_output.get("url")
                self._set_state(STATE_RESPONDING)
                _LOGGER.debug("TTS URL: %s", tts_url)
            elif event.type == PipelineEventType.ERROR:
                error_data = event.data or {}
                _LOGGER.error(
                    "Pipeline error: %s - %s",
                    error_data.get("code", "unknown"),
                    error_data.get("message", ""),
                )

        stt_metadata = SpeechMetadata(
            language=language,
            format=AudioFormats.WAV,
            codec=AudioCodecs.PCM,
            bit_rate=AudioBitRates.BITRATE_16,
            sample_rate=AudioSampleRates.SAMPLERATE_16000,
            channel=AudioChannels.CHANNEL_MONO,
        )

        audio_settings = AudioSettings(silence_seconds=silence_seconds)

        await async_pipeline_from_audio_stream(
            self.hass,
            context=Context(),
            event_callback=event_callback,
            stt_metadata=stt_metadata,
            stt_stream=self._wyoming_audio_stream(reader),
            pipeline_id=pipeline_id,
            tts_audio_output="mp3",
            audio_settings=audio_settings,
            start_stage=PipelineStage.STT,
            end_stage=PipelineStage.TTS,
        )

        return tts_url

    async def _wyoming_audio_stream(
        self, reader: asyncio.StreamReader
    ) -> AsyncGenerator[bytes, None]:
        """Read audio chunks from Wyoming service and yield raw PCM bytes."""
        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(
                        async_read_event(reader), timeout=WYOMING_READ_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    _LOGGER.debug("Wyoming audio read timeout")
                    break

                if event is None:
                    _LOGGER.debug("Wyoming connection closed")
                    break

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    yield chunk.audio
                elif AudioStop.is_type(event.type):
                    _LOGGER.debug("Wyoming audio stop received")
                    break

                # Handle satellite-specific events gracefully
                try:
                    from wyoming.satellite import StreamingStarted, StreamingStopped

                    if StreamingStarted.is_type(event.type):
                        _LOGGER.debug("Satellite streaming started")
                        continue
                    if StreamingStopped.is_type(event.type):
                        _LOGGER.debug("Satellite streaming stopped")
                        break
                except ImportError:
                    pass

        except (OSError, ConnectionError):
            _LOGGER.debug("Wyoming connection lost during audio streaming")

    async def _play_tts(self, tts_url: str) -> None:
        """Play TTS audio on the configured media player."""
        media_player = self._config[CONF_MEDIA_PLAYER]

        # Make URL absolute if it's a relative path
        if tts_url.startswith("/"):
            try:
                base_url = get_url(self.hass)
                tts_url = f"{base_url}{tts_url}"
            except Exception:
                _LOGGER.warning(
                    "Could not determine HA base URL; using relative TTS URL"
                )

        _LOGGER.debug("Playing TTS on %s: %s", media_player, tts_url)

        await self.hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": media_player,
                "media_content_id": tts_url,
                "media_content_type": "music",
            },
            blocking=True,
        )
