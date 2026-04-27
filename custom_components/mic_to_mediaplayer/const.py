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

# Phrases that force-end a conversation regardless of the agent's
# continue_conversation flag. Matched as case-insensitive substrings on the
# trimmed STT text.
CONVERSATION_CLOSE_PHRASES = (
    # English
    "that's all",
    "thats all",
    "that is all",
    "bye",
    "goodbye",
    "good bye",
    "stop",
    "nevermind",
    "never mind",
    "thanks jarvis",
    "thank you jarvis",
    "thank you, jarvis",
    "we're done",
    "we are done",
    "i'm done",
    "im done",
    # German
    "tschüss",
    "tschuess",
    "tschüs",
    "auf wiedersehen",
    "danke jarvis",
    "danke, jarvis",
    "danke dir",
    "das war's",
    "das wars",
    "das war es",
    "fertig",
    "ende",
    "beenden",
    "schluss",
    "stopp",
)
