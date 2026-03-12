# Mic to MediaPlayer

Home Assistant Custom Integration: Nutze ein über das **Wyoming Protocol** eingebundenes Mikrofon für Spracheingabe und spiele die TTS-Antwort deines Assistenten auf einem beliebigen **Media Player** ab.

## Features

- **Wyoming-Mikrofon als Eingang**: Verbindet sich direkt mit einem Wyoming-Dienst (Satellite/Mikrofon) per TCP
- **Assist-Pipeline-Integration**: Nutzt die eingebaute Home Assistant Assist Pipeline (STT → Conversation → TTS)
- **Flexible Media-Player-Ausgabe**: TTS-Antwort wird auf einem frei wählbaren Media Player abgespielt
- **Push-to-Talk Button**: Ein Button-Entity startet die Sprachaufnahme per Klick oder Automation
- **Status-Sensor**: Zeigt den aktuellen Pipeline-Status (Bereit, Höre zu, Verarbeite, Antwort, Fehler)
- **Konfigurierbarer Stille-Timeout**: VAD-basierte Erkennung, wann die Spracheingabe endet
- **Service-Aufruf**: `mic_to_mediaplayer.listen` kann in Automationen verwendet werden
- **HACS-kompatibel**: Einfache Installation über HACS

## Voraussetzungen

- Home Assistant 2024.1.0 oder neuer
- Ein Wyoming-kompatibler Mikrofon-Dienst (z.B. [wyoming-satellite](https://github.com/rhasspy/wyoming-satellite))
- Eine konfigurierte Assist-Pipeline mit STT und TTS (z.B. Whisper + Piper)
- Ein Media Player in Home Assistant (z.B. Sonos, Google Cast, DLNA, etc.)

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
3. Gib die Konfiguration ein:
   - **Wyoming Host**: IP-Adresse deines Wyoming-Dienstes (z.B. `192.168.1.100`)
   - **Wyoming Port**: Port des Wyoming-Dienstes (Standard: `10700`)
   - **Media Player**: Wähle den Media Player für die TTS-Ausgabe
   - **Assist-Pipeline**: Wähle die gewünschte Pipeline (oder Standard)
   - **Sprache**: Optional – z.B. `de` für Deutsch
   - **Stille-Erkennung**: Sekunden Stille bis die Aufnahme endet (Standard: 3s)

## Verwendung

### Button-Entity

Die Integration erstellt einen "Zuhören starten" Button. Drücke ihn im Dashboard oder nutze ihn in Automationen:

```yaml
service: button.press
target:
  entity_id: button.mic_192_168_1_100_10700_media_player_wohnzimmer_zuhoren_starten
```

### Service-Aufruf

```yaml
service: mic_to_mediaplayer.listen
```

### Automation Beispiel

```yaml
automation:
  - alias: "Sprachsteuerung per Knopfdruck"
    trigger:
      - platform: state
        entity_id: binary_sensor.physischer_button
        to: "on"
    action:
      - service: mic_to_mediaplayer.listen
```

### Status-Sensor

Der Sensor `sensor.*_pipeline_status` zeigt den aktuellen Zustand:
- **Bereit** – Wartet auf Eingabe
- **Verbinde...** – Verbindet mit Wyoming-Dienst
- **Höre zu...** – Nimmt Sprache auf
- **Verarbeite...** – STT und Conversation laufen
- **Antwort wird abgespielt** – TTS wird auf dem Media Player abgespielt
- **Fehler** – Ein Fehler ist aufgetreten

Zusätzliche Attribute:
- `last_speech_text`: Letzter erkannter Sprachtext
- `last_response`: Letzte Antwort des Assistenten

## Architektur

```
Wyoming Mikrofon ──TCP──→ [Integration] ──→ Assist Pipeline (STT → Intent → TTS)
                                                        │
                                                        ↓
                                                   Media Player ♪
```

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
