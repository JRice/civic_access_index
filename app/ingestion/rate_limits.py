import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def with_simple_delay(call: Callable[[], Awaitable[T]], delay_seconds: float = 0.25) -> T:
    await asyncio.sleep(delay_seconds)
    return await call()

