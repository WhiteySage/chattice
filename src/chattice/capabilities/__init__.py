"""Capability model: response channel, outbound operations, preview features."""

from .matrix import (
    PREVIEW_APP_COMMAND_TYPES,
    CapabilityNotSupported,
    OutboundCapabilities,
    OutboundCapability,
    PreviewCapabilities,
    PreviewFeature,
    ResponseCapabilities,
    ResponseCapability,
    can_open_dialog,
)

__all__ = [
    "PREVIEW_APP_COMMAND_TYPES",
    "CapabilityNotSupported",
    "OutboundCapabilities",
    "OutboundCapability",
    "PreviewCapabilities",
    "PreviewFeature",
    "ResponseCapabilities",
    "ResponseCapability",
    "can_open_dialog",
]
