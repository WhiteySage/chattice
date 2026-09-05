"""FastAPI integration (optional extra chattice[fastapi])."""

from .router import (
    create_chat_router,
    create_pubsub_router,
    create_workspace_events_router,
)

__all__ = [
    "create_chat_router",
    "create_pubsub_router",
    "create_workspace_events_router",
]
