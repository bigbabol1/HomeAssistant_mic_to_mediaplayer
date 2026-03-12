"""Constants for the Mic to MediaPlayer integration."""

DOMAIN = "mic_to_mediaplayer"

# Configuration keys
CONF_WYOMING_HOST = "wyoming_host"
CONF_WYOMING_PORT = "wyoming_port"
CONF_MEDIA_PLAYER = "media_player_entity_id"
CONF_PIPELINE_ID = "pipeline_id"
CONF_LANGUAGE = "language"
CONF_SILENCE_SECONDS = "silence_seconds"

# Defaults
DEFAULT_PORT = 10700
DEFAULT_SILENCE_SECONDS = 3.0

# Pipeline states
STATE_IDLE = "idle"
STATE_CONNECTING = "connecting"
STATE_LISTENING = "listening"
STATE_PROCESSING = "processing"
STATE_RESPONDING = "responding"
STATE_ERROR = "error"

# Platforms
PLATFORMS = ["button", "sensor"]
