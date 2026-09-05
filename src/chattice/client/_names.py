"""Canonicalization of Google Chat resource names (internal).

Shared by the Bot surface and the resource clients; kept in a leaf
module so neither import direction creates a package cycle.
"""

from __future__ import annotations

from chattice.events import SpaceRef, UserRef

from .errors import ChatAPIError


def _canonical_space(space: SpaceRef | str) -> str:
    """Validate and canonicalize a space target.

    One resource-name policy: a bare space ID is wrapped into the
    canonical ``spaces/{id}`` form (as the identifier docs promise),
    an already-canonical name passes through, malformed values raise
    locally — no network lookups, no remote errors replacing local
    validation.
    """
    name = space if isinstance(space, str) else space.name
    if name is None:
        raise ChatAPIError("SpaceRef has no name; cannot target a space")
    parent = name.strip()
    if not parent:
        raise ChatAPIError("space must be a non-empty identifier")
    if "/" in parent:
        if not parent.startswith("spaces/") or parent.count("/") != 1:
            raise ChatAPIError(
                "space must be a bare space ID or a canonical "
                "'spaces/{id}' resource name; got {parent!r}"
            )
        return parent
    return f"spaces/{parent}"


def _canonical_user(user: UserRef | str, *, parameter: str = "private_to") -> str:
    """Validate and canonicalize a user target.

    An empty string or a nameless ``UserRef`` must FAIL CLOSED — it
    could otherwise produce a public message. A bare user ID is wrapped into
    the canonical ``users/{id}`` resource form; already-canonical names
    pass through; malformed values (whitespace, misplaced slashes) raise
    before any transport work.
    """
    name = user if isinstance(user, str) else user.name
    if name is None:
        raise ChatAPIError(f"{parameter} UserRef has no name; cannot target a user")
    viewer = name.strip()
    if not viewer:
        raise ChatAPIError(f"{parameter} must be a non-empty user identifier")
    if "/" in viewer:
        if not viewer.startswith("users/") or viewer.count("/") != 1:
            raise ChatAPIError(
                f"{parameter} must be a bare user ID or a canonical "
                f"'users/{{id}}' resource name; got {viewer!r}"
            )
        return viewer
    return f"users/{viewer}"
