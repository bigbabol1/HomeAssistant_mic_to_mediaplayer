"""Constants for the Mic to MediaPlayer integration."""

DOMAIN = "mic_to_mediaplayer"

# Configuration keys
CONF_SATELLITE_ENTITY = "satellite_entity_id"
CONF_MEDIA_PLAYER = "media_player_entity_id"
CONF_PIPELINE_ID = "pipeline_id"

# Pipeline states
STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_PROCESSING = "processing"
STATE_RESPONDING = "responding"
STATE_ERROR = "error"

# Platforms
PLATFORMS = ["sensor"]
