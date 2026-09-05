"""Tests for the discovery-document registry verifier."""

from scripts.verify_registry import collect_methods, compare_with_discovery

DISCOVERY = {
    "methods": {
        "spaces.messages.create": {
            "scopes": ["https://www.googleapis.com/auth/chat.bot"]
        },
        "spaces.list": {"scopes": ["https://www.googleapis.com/auth/chat.bot"]},
    }
}


def test_missing_method_is_flagged() -> None:
    report = compare_with_discovery(
        google_methods=DISCOVERY["methods"],
        registry_methods={"spaces.messages.create", "spaces.list", "spaces.foo"},
        registry_scopes={},
    )
    assert report["missing"] == ["spaces.foo"]
    assert report["scope_mismatches"] == []


def test_unknown_scope_is_flagged() -> None:
    report = compare_with_discovery(
        google_methods={"spaces.list": {"scopes": [".../chat.bot"]}},
        registry_methods={"spaces.list"},
        registry_scopes={"spaces.list": {".../chat.bot", ".../chat.import"}},
    )
    assert report["missing"] == []
    assert report["scope_mismatches"] == ["spaces.list"]


def test_fabricated_method_is_flagged() -> None:
    """A fabricated operation (e.g. a non-existent getAvailability)
    surfaces as a missing method."""
    report = compare_with_discovery(
        google_methods=DISCOVERY["methods"],
        registry_methods={"spaces.getAvailability"},
        registry_scopes={},
    )
    assert report["missing"] == ["spaces.getAvailability"]
    assert report["scope_mismatches"] == []


def test_collect_methods_walks_nested_resources() -> None:
    document = {
        "resources": {
            "spaces": {
                "methods": {"list": {"scopes": []}},
                "resources": {
                    "messages": {
                        "methods": {"create": {"scopes": []}},
                    },
                    "members": {
                        "methods": {"list": {"scopes": []}},
                    },
                },
            },
            "media": {
                "methods": {"upload": {"scopes": []}},
            },
        }
    }
    methods = collect_methods(document)
    assert set(methods) == {
        "spaces.list",
        "spaces.messages.create",
        "spaces.members.list",
        "media.upload",
    }


def test_collect_methods_ignores_empty_method_sets() -> None:
    methods = collect_methods({"resources": {"spaces": {"methods": {}}}})
    assert methods == {}
