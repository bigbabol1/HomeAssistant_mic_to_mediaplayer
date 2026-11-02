"""Constants for the Mic to MediaPlayer integration."""

DOMAIN = "mic_to_mediaplayer"

# Configuration keys
CONF_SATELLITE_ENTITY = "satellite_entity_id"
CONF_MEDIA_PLAYER = "media_player_entity_id"
CONF_PIPELINE_ID = "pipeline_id"
CONF_OUTPUT_FORMAT = "output_format"

# Audio format sent to the media player
OUTPUT_FORMAT_AUTO = "auto"
OUTPUT_FORMAT_MP3 = "mp3"
OUTPUT_FORMAT_WAV = "wav"
OUTPUT_FORMAT_ORIGINAL = "original"
OUTPUT_FORMATS = [
    OUTPUT_FORMAT_AUTO,
    OUTPUT_FORMAT_MP3,
    OUTPUT_FORMAT_WAV,
    OUTPUT_FORMAT_ORIGINAL,
]

# Pipeline states
STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_PROCESSING = "processing"
STATE_RESPONDING = "responding"
STATE_ERROR = "error"

# Platforms
PLATFORMS = ["sensor"]
