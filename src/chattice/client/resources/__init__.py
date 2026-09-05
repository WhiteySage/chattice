"""Identity-bound resource clients over the curated outbound facade."""

from chattice.client.resources.attachments import Attachments
from chattice.client.resources.base import ResourceClient
from chattice.client.resources.memberships import Memberships
from chattice.client.resources.messages import Messages
from chattice.client.resources.reactions import Reactions
from chattice.client.resources.spaces import Spaces
from chattice.client.resources.users import Users

__all__ = [
    "Attachments",
    "Memberships",
    "Messages",
    "Reactions",
    "ResourceClient",
    "Spaces",
    "Users",
]
