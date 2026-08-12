"""
CYNEXIS — Vision Subsystem Unit Tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from AI.Vision.provider import MockVisionProvider
from AI.Vision.vlm import LocalVLMProvider
from AI.Intent.engine import intent_engine
from core.constants import ActionName
from AI.Actions.actions import inject_controllers, action_describe_scene
from Backend.Vision.camera import MockCamera


@pytest.mark.asyncio
async def test_mock_vision_provider_lifecycle():
    provider = MockVisionProvider()
    assert provider.is_loaded() is False

    await provider.load()
    assert provider.is_loaded() is True

    desc = await provider.describe_image(b"MOCK_IMAGE_DATA")
    assert isinstance(desc, str)
    assert len(desc) > 0

    await provider.unload()
    assert provider.is_loaded() is False


@pytest.mark.asyncio
async def test_local_vlm_provider_lifecycle():
    vlm = LocalVLMProvider()
    assert vlm.is_loaded() is False

    await vlm.load()
    assert vlm.is_loaded() is True

    desc = await vlm.describe_image(b"")
    assert "No optical input" in desc

    await vlm.unload()
    assert vlm.is_loaded() is False


def test_describe_scene_intent_classification():
    queries = [
        "CYNEXIS, what do you see?",
        "describe what you see",
        "what are you seeing right now",
        "look around",
        "what's in front of you",
    ]
    for q in queries:
        action = intent_engine.classify(q)
        assert action == ActionName.DESCRIBE_SCENE


@pytest.mark.asyncio
async def test_action_describe_scene():
    camera = MockCamera()
    await camera.start()
    vision = MockVisionProvider()
    await vision.load()

    inject_controllers(camera=camera, vision=vision)

    result = await action_describe_scene()
    assert "speech" in result
    assert "description" in result
    assert len(result["description"]) > 0
