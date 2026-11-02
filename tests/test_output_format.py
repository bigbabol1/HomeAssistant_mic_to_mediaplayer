"""The audio format sent to the media player."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.components import tts

from custom_components.mic_to_mediaplayer.interceptor import PipelineInterceptor

FLAC_URL = "/api/tts_proxy/abc.flac"
OUTPUT = {"token": "abc.flac", "url": FLAC_URL}


@pytest.fixture(autouse=True)
def pipeline_stream():
    """Give the TTS stubs a pipeline stream and a new stream to hand out."""
    tts.async_get_stream.side_effect = None
    tts.async_create_stream.side_effect = None
    tts.async_get_stream.return_value = SimpleNamespace(
        engine="tts.cloud",
        language="en-US",
        options={
            "voice": "LunaNeural",
            "preferred_format": "flac",
            "preferred_sample_rate": 48000,
            "preferred_sample_channels": 1,
            "preferred_sample_bytes": 2,
        },
    )
    tts.async_create_stream.reset_mock()
    new_stream = MagicMock(url="/api/tts_proxy/new.mp3")
    tts.async_create_stream.return_value = new_stream
    return new_stream


def interceptor(output_format="auto", sonos=False, text="It is ten past four."):
    result = PipelineInterceptor(
        MagicMock(), "assist_satellite.a", "media_player.b", None, output_format
    )
    result._is_sonos = sonos
    result._tts_text = text
    return result


@pytest.mark.parametrize(
    ("output_format", "sonos", "url", "wanted"),
    [
        ("auto", True, FLAC_URL, "mp3"),
        ("auto", True, "/api/tts_proxy/abc.mp3", None),
        ("auto", True, "/api/tts_proxy/abc.wav", None),
        ("auto", True, "/api/tts_proxy/abc.FLAC", "mp3"),
        ("auto", False, FLAC_URL, None),
        ("original", True, FLAC_URL, None),
        ("mp3", False, FLAC_URL, "mp3"),
        ("mp3", False, "/api/tts_proxy/abc.mp3", None),
        ("wav", False, FLAC_URL, "wav"),
        ("wav", True, "/api/tts_proxy/abc.mp3", "wav"),
    ],
)
def test_wanted_format(output_format, sonos, url, wanted):
    assert interceptor(output_format, sonos)._wanted_format(url) == wanted


def test_new_stream_keeps_engine_language_voice_and_text(pipeline_stream):
    url = interceptor("auto", sonos=True)._url_in_output_format(FLAC_URL, OUTPUT)

    assert url == "/api/tts_proxy/new.mp3"
    args = tts.async_create_stream.call_args.args
    assert args[1:3] == ("tts.cloud", "en-US")
    assert args[3] == {"voice": "LunaNeural", "preferred_format": "mp3"}
    pipeline_stream.async_set_message.assert_called_once_with("It is ten past four.")


def test_players_that_need_no_conversion_get_no_second_synthesis():
    url = interceptor("auto", sonos=False)._url_in_output_format(FLAC_URL, OUTPUT)

    assert url == FLAC_URL
    tts.async_create_stream.assert_not_called()


def test_a_chime_is_not_replaced_by_speech():
    ic = interceptor("auto", sonos=True, text="unused")
    ic._process_event(
        SimpleNamespace(
            type="tts-start",
            data={"tts_input": "Turned on the light", "acknowledge_override": True},
        )
    )

    assert ic._url_in_output_format(FLAC_URL, OUTPUT) == FLAC_URL
    tts.async_create_stream.assert_not_called()


def test_text_comes_from_this_runs_tts_start(pipeline_stream):
    ic = interceptor("auto", sonos=True, text="last run")
    ic._process_event(SimpleNamespace(type="run-start", data={}))
    assert ic._tts_text is None
    ic._process_event(
        SimpleNamespace(type="tts-start", data={"tts_input": "this run"})
    )

    ic._url_in_output_format(FLAC_URL, OUTPUT)

    pipeline_stream.async_set_message.assert_called_once_with("this run")


@pytest.mark.parametrize("failure", ["no_stream", "create", "api_missing"])
def test_any_failure_plays_the_original(failure):
    if failure == "no_stream":
        tts.async_get_stream.return_value = None
    elif failure == "create":
        tts.async_create_stream.side_effect = ValueError("unsupported")
    else:
        tts.async_get_stream.side_effect = AttributeError("no async_get_stream")

    url = interceptor("mp3")._url_in_output_format(FLAC_URL, OUTPUT)

    assert url == FLAC_URL


def test_missing_token_plays_the_original():
    assert interceptor("mp3")._url_in_output_format(FLAC_URL, {"url": FLAC_URL}) == FLAC_URL
