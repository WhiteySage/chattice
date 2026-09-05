"""Public framework exceptions and routing control primitives."""

from __future__ import annotations


class ChatticeError(Exception):
    """Base class for ordinary framework failures."""


class RoutingError(ChatticeError):
    """Base class for routing configuration or execution failures."""


class RouterConfigurationError(RoutingError):
    """A router hierarchy violates ownership or acyclicity rules."""


class DependencyResolutionError(RoutingError):
    """A handler dependency cannot be resolved deterministically."""


class InvalidHandlerError(RoutingError):
    """A registered handler has an unsupported signature or return shape."""


class UnhandledInteractionError(RoutingError):
    """An interactive event matched no handler in strict-interactions mode."""


class FilterError(RoutingError):
    """A filter is invalid or returned an unsupported value."""


class ContextConflictError(FilterError):
    """Two context providers attempted to define the same dependency name."""


class AssetError(ChatticeError):
    """Base class for local Card asset failures."""


class AssetPublisherNotConfigured(AssetError):
    """A local Card image was used without an AssetPublisher."""


class AssetPublishError(AssetError):
    """A Card asset could not be read, published, or resolved to HTTPS."""


class RoutingControl(BaseException):
    """Base for explicit non-error routing control flow."""


class SkipHandler(RoutingControl):
    """Skip the current handler candidate and continue routing."""


class StopPropagation(RoutingControl):
    """Stop routing the current event without invoking more handlers."""


__all__ = [
    "AssetError",
    "AssetPublishError",
    "AssetPublisherNotConfigured",
    "ChatticeError",
    "ContextConflictError",
    "DependencyResolutionError",
    "FilterError",
    "InvalidHandlerError",
    "RouterConfigurationError",
    "RoutingControl",
    "RoutingError",
    "SkipHandler",
    "StopPropagation",
    "UnhandledInteractionError",
]
