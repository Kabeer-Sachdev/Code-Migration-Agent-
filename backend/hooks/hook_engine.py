"""
Hook Engine - async event bus for migration lifecycle events.
Broadcasts events to registered handlers and live WebSocket connections.
"""
import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    MIGRATION_START     = "MIGRATION_START"
    FILES_UPLOADED      = "FILES_UPLOADED"
    ANALYSIS_DONE       = "ANALYSIS_DONE"
    RAG_RETRIEVED       = "RAG_RETRIEVED"
    LLM_GENERATING      = "LLM_GENERATING"
    LLM_STREAM          = "LLM_STREAM"
    CONVERSION_DONE     = "CONVERSION_DONE"
    TESTS_GENERATED     = "TESTS_GENERATED"
    PACKAGING           = "PACKAGING"
    MIGRATION_COMPLETE  = "MIGRATION_COMPLETE"
    MIGRATION_ERROR     = "MIGRATION_ERROR"


class HookEngine:
    """
    Central event bus for the migration agent.
    Supports both static handler registration and dynamic WebSocket callbacks.
    """

    def __init__(self):
        self._handlers: Dict[HookEvent, List[Callable]] = {e: [] for e in HookEvent}
        # Per-job WebSocket callbacks: job_id -> list of async callables
        self._ws_callbacks: Dict[str, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def on(self, event: HookEvent, handler: Callable) -> None:
        """Register a static handler for a lifecycle event."""
        self._handlers[event].append(handler)

    def add_ws_callback(self, job_id: str, callback: Callable) -> None:
        """Register a WebSocket callback for a specific job."""
        self._ws_callbacks.setdefault(job_id, []).append(callback)

    def remove_ws_callback(self, job_id: str, callback: Callable) -> None:
        """Remove a WebSocket callback when the connection closes."""
        callbacks = self._ws_callbacks.get(job_id, [])
        if callback in callbacks:
            callbacks.remove(callback)

    # ------------------------------------------------------------------
    # Event firing
    # ------------------------------------------------------------------

    async def fire(
        self,
        event: HookEvent,
        data: Any = None,
        job_id: str | None = None,
        message: str | None = None,
    ) -> None:
        """Fire an event, calling all registered handlers and WebSocket listeners."""
        logger.info("[Hook] %s | job=%s | %s", event.value, job_id, message or "")

        payload = {
            "event": event.value,
            "job_id": job_id,
            "message": message or event.value.replace("_", " ").title(),
            "data": data,
        }

        # Call static handlers
        for handler in self._handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload)
                else:
                    handler(payload)
            except Exception as exc:
                logger.error("Hook handler raised: %s", exc)

        # Broadcast to job-specific WebSocket listeners
        if job_id:
            for cb in list(self._ws_callbacks.get(job_id, [])):
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(payload)
                    else:
                        cb(payload)
                except Exception as exc:
                    logger.error("WS callback raised: %s", exc)


# Singleton instance shared across the application
hook_engine = HookEngine()
