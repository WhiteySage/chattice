"""Proto construction helpers shared by the resource clients."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.apps.chat_v1.types.attachment import AttachmentDataRef


def _attachment_data_ref_proto(mapping: Mapping[str, object]) -> AttachmentDataRef:
    """Build the SDK proto from a wire ``attachmentDataRef`` mapping."""
    kwargs: dict[str, Any] = {}
    resource_name = mapping.get("resourceName") or mapping.get("resource_name")
    if isinstance(resource_name, str) and resource_name:
        kwargs["resource_name"] = resource_name
    upload_token = mapping.get("attachmentUploadToken") or mapping.get(
        "attachment_upload_token"
    )
    if isinstance(upload_token, str) and upload_token:
        kwargs["attachment_upload_token"] = upload_token
    return AttachmentDataRef(**kwargs)
