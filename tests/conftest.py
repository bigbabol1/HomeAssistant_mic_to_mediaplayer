"""Stub the homeassistant modules, so the tests run without Home Assistant."""

import enum
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


class PipelineEventType(enum.StrEnum):
    """The event types the interceptor handles."""

    RUN_START = "run-start"
    STT_START = "stt-start"
    STT_END = "stt-end"
    INTENT_END = "intent-end"
    TTS_START = "tts-start"
    TTS_END = "tts-end"
    RUN_END = "run-end"
    ERROR = "error"


def _module(name: str, **attrs) -> MagicMock:
    module = MagicMock(name=name)
    module.__name__ = name
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


tts = _module("homeassistant.components.tts", ATTR_PREFERRED_FORMAT="preferred_format")
_module("homeassistant")
_module("homeassistant.components", tts=tts)
_module(
    "homeassistant.components.assist_pipeline",
    PipelineEvent=object,
    PipelineEventType=PipelineEventType,
)
_module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
for name in (
    "voluptuous",
    "homeassistant.const",
    "homeassistant.config_entries",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.entity_registry",
    "homeassistant.helpers.event",
    "homeassistant.helpers.network",
):
    _module(name)
