from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors, types

from app.imagegen.base import ImageGenBlocked, ImageGenNoImage, ImageGenUnavailable
from app.imagegen.gemini import GeminiImageGen, build_contents, parse_response
from tests.conftest import make_image

MODEL = "gemini-nano-banana-2.1"


def response(
    parts: list[types.Part],
    finish_reason: types.FinishReason = types.FinishReason.STOP,
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts), finish_reason=finish_reason
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1500,
            candidates_token_count=1680,
            thoughts_token_count=200,
            total_token_count=3380,
            prompt_tokens_details=[
                types.ModalityTokenCount(modality=types.MediaModality.TEXT, token_count=468),
                types.ModalityTokenCount(modality=types.MediaModality.IMAGE, token_count=1032),
            ],
            candidates_tokens_details=[
                types.ModalityTokenCount(modality=types.MediaModality.IMAGE, token_count=1680),
            ],
        ),
    )


def image_part(data: bytes, *, thought: bool = False) -> types.Part:
    return types.Part(inline_data=types.Blob(data=data, mime_type="image/png"), thought=thought)


def test_parse_response_skips_thought_images_and_reads_usage() -> None:
    final = make_image((1856, 2304), format="PNG")
    parsed = parse_response(
        response([image_part(b"draft", thought=True), types.Part(text="Here"), image_part(final)]),
        MODEL,
    )

    assert parsed.data == final
    assert parsed.mime == "image/png"
    assert parsed.provider == "gemini"
    assert parsed.model == MODEL
    assert parsed.finish_reason == "STOP"
    assert parsed.usage == {
        "prompt_tokens": 1500,
        "output_tokens": 1680,
        "thoughts_tokens": 200,
        "total_tokens": 3380,
        "prompt_text_tokens": 468,
        "prompt_image_tokens": 1032,
        "output_image_tokens": 1680,
    }


def test_parse_response_raises_blocked_on_image_safety() -> None:
    with pytest.raises(ImageGenBlocked) as raised:
        parse_response(
            response([types.Part(text="I can't")], types.FinishReason.IMAGE_SAFETY), MODEL
        )

    assert raised.value.reason == "IMAGE_SAFETY"


def test_parse_response_raises_no_image_when_only_text_comes_back() -> None:
    with pytest.raises(ImageGenNoImage):
        parse_response(response([types.Part(text="Sure!")]), MODEL)


def test_parse_response_raises_blocked_when_the_prompt_is_blocked() -> None:
    blocked = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason.PROHIBITED_CONTENT
        )
    )

    with pytest.raises(ImageGenBlocked, match="PROHIBITED_CONTENT"):
        parse_response(blocked, MODEL)


def test_build_contents_labels_products_and_puts_the_style_reference_last() -> None:
    product = make_image((100, 125))
    style = make_image((100, 125), format="PNG")

    parts = build_contents("prompt", [product, product], style)

    assert [part.text for part in parts if part.text] == [
        "prompt",
        "Product reference 1:",
        "Product reference 2:",
        "Style reference:",
    ]
    assert parts[-1].inline_data.mime_type == "image/png"
    assert parts[2].inline_data.mime_type == "image/jpeg"


def fake_client(generate_content: Any) -> Any:
    return SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )


async def test_generate_sends_model_and_4_5_2k_config() -> None:
    calls: list[dict[str, Any]] = []

    async def generate_content(**kwargs: Any) -> types.GenerateContentResponse:
        calls.append(kwargs)
        return response([image_part(b"image")])

    adapter = GeminiImageGen(
        fake_client(generate_content), MODEL, "minimal", "2K", max_concurrency=2
    )
    result = await adapter.generate("prompt", [make_image((100, 125))])

    assert result.data == b"image"
    config: types.GenerateContentConfig = calls[0]["config"]
    assert calls[0]["model"] == MODEL
    assert config.image_config.aspect_ratio == "4:5"
    assert config.image_config.image_size == "2K"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL


async def test_generate_maps_api_errors_to_unavailable() -> None:
    async def generate_content(**kwargs: Any) -> types.GenerateContentResponse:
        raise errors.ClientError(
            429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
        )

    adapter = GeminiImageGen(
        fake_client(generate_content), MODEL, "medium", "2K", max_concurrency=1
    )

    with pytest.raises(ImageGenUnavailable, match="429 RESOURCE_EXHAUSTED"):
        await adapter.generate("prompt", [])
