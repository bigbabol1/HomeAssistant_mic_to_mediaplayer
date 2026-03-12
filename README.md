# Mic to MediaPlayer

Hier ist sie endlich - die Integration, die es dir ermöglicht deine Assist-Pipeline so zu konfigurieren, wie du es möchtest!

Home Assistant Custom Integration: Nutze jede **Assist Satellite** Entität (z.B. die **Assist Microphone** App, Wyoming Satellites, ESPHome Satellites) als Spracheingabe und spiele die TTS-Antwort des Assistenten auf einem beliebigen **Media Player** ab.

## Features

- **Jeder Assist Satellite nutzbar**: Funktioniert mit allen `assist_satellite`-Entitäten – Assist Microphone App, Wyoming Satellites, ESPHome Voice Satellites, VoIP Satellites
- **Flexible Media-Player-Ausgabe**: TTS-Antwort wird auf einem frei wählbaren Media Player abgespielt (Sonos, Google Cast, DLNA, etc.)
- **Nicht-invasiv**: Klinkt sich über Instance-Level Patching in die bestehende Satellite-Entität ein, ohne globale Funktionen zu ändern
- **Status-Sensor**: Zeigt den aktuellen Pipeline-Status (Bereit, Höre zu, Verarbeite, Antwort, Fehler) sowie den letzten erkannten Text und die Antwort
- **Automatische Erkennung**: Wartet bei HA-Start automatisch auf die Verfügbarkeit der Satellite-Entität
- **Mehrfach konfigurierbar**: Mehrere Satellite → Media Player Zuordnungen gleichzeitig möglich
- **HACS-kompatibel**: Einfache Installation über HACS

## Voraussetzungen

- Home Assistant 2024.10.0 oder neuer (für `assist_satellite`-Unterstützung)
- Eine konfigurierte `assist_satellite`-Entität, z.B.:
  - [Assist Microphone](https://www.home-assistant.io/voice_control/android/) (HA Companion App)
  - [Wyoming Satellite](https://github.com/rhasspy/wyoming-satellite)
  - [ESPHome Voice Satellite](https://esphome.io/components/voice_assistant/)
- Eine konfigurierte Assist-Pipeline mit STT und TTS (z.B. Whisper + Piper)
- Ein Media Player in Home Assistant

## Installation

### HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Klicke auf "Integrationen" → "Benutzerdefinierte Repositories"
3. Füge `https://github.com/bigbabol1/HomeAssistant_mic_to_mediaplayer` als Repository hinzu (Kategorie: Integration)
4. Installiere "Mic to MediaPlayer"
5. Starte Home Assistant neu

### Manuell

1. Kopiere den Ordner `custom_components/mic_to_mediaplayer` in dein Home Assistant `config/custom_components/` Verzeichnis
2. Starte Home Assistant neu

## Einrichtung

1. Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen**
2. Suche nach "Mic to MediaPlayer"
3. Konfiguriere:
   - **Assist Satellite**: Wähle die Satellite-Entität (z.B. dein Smartphone mit der Assist Microphone App)
   - **Media Player**: Wähle den Media Player für die TTS-Ausgabe

Das war's! Die Integration klinkt sich automatisch in die Pipeline-Events der gewählten Satellite-Entität ein und spielt jede TTS-Antwort auf dem Media Player ab.

## Funktionsweise

```
Assist Satellite (Mikrofon)
        │
        │ Spracheingabe → Assist Pipeline (STT → Conversation → TTS)
        │
        ├──→ Satellite spielt TTS ab (normal)
        │
        └──→ [Mic to MediaPlayer] fängt TTS-URL ab
                       │
                       ↓
                  Media Player ♪
```

Die Integration nutzt **Instance-Level Patching** auf der `on_pipeline_event`-Methode der gewählten Satellite-Entität. Dadurch:
- Werden Pipeline-Events (STT, Intent, TTS) abgefangen
- Wird die TTS-URL bei Generierung erfasst
- Wird die TTS-Audio auf dem Media Player abgespielt
- Bleibt das Original-Verhalten des Satellites vollständig erhalten

## Status-Sensor

Der Sensor `sensor.*_pipeline_status` zeigt:

| Status | Bedeutung |
|---|---|
| **Bereit** | Wartet auf Spracheingabe |
| **Höre zu...** | Sprache wird aufgenommen |
| **Verarbeite...** | STT und Conversation laufen |
| **Antwort wird abgespielt** | TTS wird auf dem Media Player abgespielt |
| **Fehler** | Ein Fehler ist aufgetreten |

**Zusätzliche Attribute:**
- `last_speech_text`: Letzter erkannter Sprachtext
- `last_response`: Letzte Antwort des Assistenten
- `satellite_entity`: Die überwachte Satellite-Entität
- `media_player_entity`: Der Ziel-Media-Player
- `interceptor_active`: Ob die Interception aktiv ist

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
