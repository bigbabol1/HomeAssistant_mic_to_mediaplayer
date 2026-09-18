# Mic to MediaPlayer

Here it finally is: the integration that lets you set up your Assist pipeline exactly the way you want!

Home Assistant custom integration: use any **Assist Satellite** entity (e.g. the **Assist Microphone** app, Wyoming satellites, ESPHome satellites) for voice input and play the assistant's TTS response on any **media player**.

## Features

- **Works with any Assist Satellite**: supports every `assist_satellite` entity: the Assist Microphone app, Wyoming satellites, ESPHome voice satellites, VoIP satellites
- **Flexible media player output**: the TTS response plays on a media player of your choice (Sonos, Google Cast, DLNA, etc.)
- **Non-invasive**: hooks into the existing satellite entity via instance-level patching, without changing any global functions
- **Status sensor**: shows the current pipeline status (ready, listening, processing, responding, error) along with the last recognized text and the response
- **Automatic detection**: on Home Assistant startup, automatically waits for the satellite entity to become available
- **Multiple instances**: several satellite → media player mappings can run at the same time
- **HACS-compatible**: easy installation via HACS

## Requirements

- Home Assistant 2024.10.0 or newer (for `assist_satellite` support)
- A configured `assist_satellite` entity, e.g.:
  - [Assist Microphone](https://www.home-assistant.io/voice_control/android/) (HA Companion app)
  - [Wyoming Satellite](https://github.com/rhasspy/wyoming-satellite)
  - [ESPHome Voice Satellite](https://esphome.io/components/voice_assistant/)
- A configured Assist pipeline with STT and TTS (e.g. Whisper + Piper)
- A media player in Home Assistant

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click "Integrations" → "Custom repositories"
3. Add `https://github.com/bigbabol1/HomeAssistant_mic_to_mediaplayer` as a repository (category: Integration)
4. Install "Mic to MediaPlayer"
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/mic_to_mediaplayer` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & services** → **Add integration**
2. Search for "Mic to MediaPlayer"
3. Configure:
   - **Assist Satellite**: select the satellite entity (e.g. your smartphone running the Assist Microphone app)
   - **Media Player**: select the media player for TTS output

That's it! The integration automatically hooks into the pipeline events of the selected satellite entity and plays every TTS response on the media player.

## How it works

```
Assist Satellite (microphone)
        │
        │ Voice input → Assist pipeline (STT → Conversation → TTS)
        │
        ├──→ Satellite plays TTS (as usual)
        │
        └──→ [Mic to MediaPlayer] intercepts the TTS URL
                       │
                       ↓
                  Media Player ♪
```

The integration uses **instance-level patching** on the `on_pipeline_event` method of the selected satellite entity. As a result:
- Pipeline events (STT, intent, TTS) are intercepted
- The TTS URL is captured as soon as it is generated
- The TTS audio is played on the media player
- The satellite's original behavior is fully preserved

## Status sensor

The `sensor.*_pipeline_status` sensor reports the following states (the state values themselves are currently in German):

| State | Meaning |
|---|---|
| **Bereit** | Ready, waiting for voice input |
| **Höre zu...** | Listening, speech is being recorded |
| **Verarbeite...** | Processing, STT and conversation are running |
| **Antwort wird abgespielt** | Responding, TTS is playing on the media player |
| **Fehler** | Error, something went wrong |

**Additional attributes:**
- `last_speech_text`: last recognized speech text
- `last_response`: the assistant's last response
- `satellite_entity`: the monitored satellite entity
- `media_player_entity`: the target media player
- `interceptor_active`: whether interception is active

## License

MIT License, see [LICENSE](LICENSE)
