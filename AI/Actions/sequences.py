"""
CYNEXIS — Action Sequences
Compound demonstrations using registered actions. Fully deterministic.
"""

import asyncio
from core.logger import get_logger
from AI.Actions.registry import registry

log = get_logger("actions.sequences")


async def hello_sequence() -> dict:
    """
    HELLO_SEQUENCE:
    1. Stop rover
    2. Raise arm slightly
    3. Wave
    4. Speak greeting
    5. Return arm to safe position
    """
    log.info("Starting HELLO_SEQUENCE")
    results = []

    results.append(await registry.execute("STOP"))
    await asyncio.sleep(0.3)

    results.append(await registry.execute("ARM_UP"))
    await asyncio.sleep(0.5)

    results.append(await registry.execute("WAVE"))
    await asyncio.sleep(0.5)

    results.append(await registry.execute("HELLO"))
    await asyncio.sleep(0.3)

    results.append(await registry.execute("ARM_DOWN"))

    log.info("HELLO_SEQUENCE complete")
    return {"sequence": "HELLO_SEQUENCE", "steps": len(results)}


async def introduction_sequence() -> dict:
    """
    INTRODUCTION_SEQUENCE:
    1. Stop movement
    2. Position arm
    3. Introduce
    4. Optional wave
    """
    log.info("Starting INTRODUCTION_SEQUENCE")
    results = []

    results.append(await registry.execute("STOP"))
    await asyncio.sleep(0.3)

    results.append(await registry.execute("ARM_UP"))
    await asyncio.sleep(0.3)

    results.append(await registry.execute("INTRODUCE_SELF"))
    await asyncio.sleep(1.0)

    results.append(await registry.execute("WAVE"))
    await asyncio.sleep(0.5)

    results.append(await registry.execute("ARM_DOWN"))

    log.info("INTRODUCTION_SEQUENCE complete")
    return {"sequence": "INTRODUCTION_SEQUENCE", "steps": len(results)}


# Map of sequence names to functions
SEQUENCES = {
    "HELLO_SEQUENCE": hello_sequence,
    "INTRODUCTION_SEQUENCE": introduction_sequence,
}
