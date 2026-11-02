<p align="center">
  <img src="https://raw.githubusercontent.com/bigbabol1/HomeAssistant_mic_to_mediaplayer/main/custom_components/mic_to_mediaplayer/brand/icon@2x.png" alt="Mic to MediaPlayer" width="128" height="128">
</p>

<h1 align="center">Mic to MediaPlayer</h1>

<p align="center">
  <b>Talk to any Assist satellite and hear the answer on any media player in Home Assistant.</b>
</p>

<p align="center">
  <a href="https://github.com/bigbabol1/HomeAssistant_mic_to_mediaplayer/releases/latest"><img src="https://img.shields.io/github/v/release/bigbabol1/HomeAssistant_mic_to_mediaplayer?style=flat-square&label=release" alt="Latest release"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-custom-41BDF5?style=flat-square" alt="HACS custom repository"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.10%2B-18BCF2?style=flat-square&logo=home-assistant&logoColor=white" alt="Home Assistant 2024.10 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#announce-service">Announce service</a> ·
  <a href="#status-sensor">Status sensor</a> ·
  <a href="#troubleshooting">Troubleshooting</a> ·
  <a href="https://github.com/bigbabol1/HomeAssistant_mic_to_mediaplayer/releases">Releases</a>
</p>

---

Small voice satellites have small speakers, and some have none. Mic to MediaPlayer keeps the satellite as your microphone and plays the assistant's reply on a speaker of your choice, such as Sonos, Google Cast or DLNA.

It attaches to the one satellite you select and changes nothing globally. Your pipeline, your satellite and your other devices keep working as before.

## Highlights

**🎙️ Works with your satellites**
- Any `assist_satellite` entity: ESPHome, Wyoming, VoIP or the Assist Microphone app.
- Several satellites at once, each with its own speaker. They can also share one.
- Reattaches by itself after a reconnect, an update or a restart.

**🔊 Plays on your speakers**
- Replies use announce mode, so players that support it resume their music afterwards.
- The right audio format for the player, with automatic MP3 for Sonos.
- Alexa devices are supported through [Alexa Media Player](https://github.com/alandtse/alexa_media_player).

**💬 Keeps the conversation natural**
- On players that report their state, the satellite is told when the speaker has finished, so the mic does not reopen over the reply.
- Follow-up questions keep listening on ESPHome satellites that offer a `start_follow_up` service.

**🧩 Fits into automations**
- An [announce service](#announce-service) speaks a message or plays a sound on a satellite's speaker.
- A [status sensor](#status-sensor) shows what the pipeline is doing, with the last question and answer.

## How it works

```text
You speak
   │
   ▼
Assist satellite ──▶ Assist pipeline (speech-to-text, agent, text-to-speech)
                                │
                                ├──▶ Satellite receives the reply as usual
                                │
                                └──▶ Mic to MediaPlayer ──▶ Your media player 🔊
```

## Quick start

### Requirements

- Home Assistant **2024.10** or newer
- [HACS](https://hacs.xyz/docs/use/)
- An `assist_satellite` entity
- An Assist pipeline with speech-to-text and text-to-speech
- A media player in Home Assistant

### Install

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bigbabol1&repository=HomeAssistant_mic_to_mediaplayer&category=integration)

1. In **HACS → ⋮ → Custom repositories**, add `https://github.com/bigbabol1/HomeAssistant_mic_to_mediaplayer` with category **Integration**. You can also use the button above.
2. Install **Mic to MediaPlayer**, then **restart Home Assistant**.
3. Add the integration:

   [![Open your Home Assistant instance and start setting up Mic to MediaPlayer.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mic_to_mediaplayer)

4. Choose a satellite and a media player. Add the integration once for each satellite.

<details>
<summary><b>Manual installation</b></summary>

<br>

Copy `custom_components/mic_to_mediaplayer` into your Home Assistant `config/custom_components/` folder, then restart Home Assistant.

</details>

## Configuration

Change these later under **Settings → Devices & services → Mic to MediaPlayer → Configure**.

| Setting | What it does |
|---------|--------------|
| **Assist satellite** | The satellite whose voice input is used. |
| **Media player** | The speaker that plays the replies. |
| **Voice assistant** | The Assist pipeline to use. The default is your preferred pipeline. |
| **Audio format** | The format sent to the media player. Only under **Configure**, see below. |

### Audio format

Satellites ask for the format they can play themselves, often FLAC, and not every media player accepts it. Sonos announcements, for example, only play MP3 and WAV.

| Option | What the player gets |
|--------|----------------------|
| **Auto** *(default)* | MP3 on Sonos, the original format on every other player |
| **MP3** or **WAV** | Always this format |
| **Original** | Always what the satellite requested |

When the format changes, the reply is synthesized a second time, as the satellite keeps its own audio. A paid text-to-speech service bills that reply twice. If this fails, the original format is played.

A Music Assistant player is not treated as Sonos, because Music Assistant handles the format itself.

## Announce service

`mic_to_mediaplayer.announce` plays something on the speaker linked to a satellite. A timer or an automation can then speak in the right room.

```yaml
action: mic_to_mediaplayer.announce
data:
  satellite_entity_id: assist_satellite.living_room
  message: "The pasta is ready"
```

| Field | Description |
|-------|-------------|
| `message` | Text to speak. Provide this or `audio_url`. |
| `audio_url` | A sound to play, such as `/local/sounds/done.mp3`. It wins if both are set. |
| `satellite_entity_id` | Which satellite's speaker to use. Needed with more than one satellite. |
| `tts_entity_id` | The text-to-speech entity. The default is the first one available. |
| `language` | The language code, such as `en` or `de`. |

## Status sensor

Each satellite gets a `sensor.*_pipeline_status` entity. Its state values are currently in German.

| State | Meaning |
|-------|---------|
| **Bereit** | Ready, waiting for voice input |
| **Höre zu...** | Listening |
| **Verarbeite...** | Processing the request |
| **Antwort wird abgespielt** | Playing the reply |
| **Fehler** | Something went wrong |

Its attributes are `last_speech_text`, `last_response`, `satellite_entity`, `media_player_entity` and `interceptor_active`.

## Troubleshooting

<details>
<summary><b>The speaker stays silent</b></summary>

<br>

Look for a warning from your speaker's integration in the Home Assistant log. Sonos, for example, reports `Sonos AudioClip announce only supports MP3 and WAV`. Set **Audio format** to MP3 and try again.

</details>

<details>
<summary><b>I hear the reply twice</b></summary>

<br>

The satellite still receives the reply, so one with its own speaker plays it too. Turn that speaker down or off on the satellite.

</details>

<details>
<summary><b>The log says "Could not attach to satellite"</b></summary>

<br>

The satellite does not exist yet, which is normal during startup. If `interceptor_active` stays false, the satellite may have been renamed or replaced. Select the current one under **Configure**.

</details>

<details>
<summary><b>The log says "duplicate_wake_up_detected"</b></summary>

<br>

Two satellites heard the same wake word and Home Assistant kept the first. This is harmless. The log line names the satellite that lost.

</details>

## License

[MIT](LICENSE)
