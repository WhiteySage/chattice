"""Facade serialization matches documented Cards v2 shapes."""

from __future__ import annotations

from chattice.cards import (
    Button,
    ButtonList,
    Card,
    CardHeader,
    Divider,
    Section,
    TextParagraph,
)


def _deploy_card() -> Card:
    return Card(
        header=CardHeader(title="Deploy production?"),
        sections=[
            Section(
                header="Actions",
                widgets=[
                    TextParagraph("Deploy v2.1 to prod?"),
                    Divider(),
                    ButtonList(
                        buttons=[
                            Button(
                                "Deploy",
                                action="deploy.confirm",
                                parameters={"env": "prod"},
                            ),
                            Button("Cancel", action="deploy.cancel"),
                        ]
                    ),
                ],
            )
        ],
    )


def test_snapshot_matches_documented_cards_v2_shape() -> None:
    data = _deploy_card().to_dict()
    assert data["header"] == {"title": "Deploy production?"}
    sections = data["sections"]
    assert sections[0]["header"] == "Actions"
    widgets = sections[0]["widgets"]
    assert widgets[0] == {"textParagraph": {"text": "Deploy v2.1 to prod?"}}
    assert widgets[1] == {"divider": {}}
    assert widgets[2]["buttonList"]["buttons"][0]["text"] == "Deploy"
    action = widgets[2]["buttonList"]["buttons"][0]["onClick"]["action"]
    assert action["function"] == "deploy.confirm"
    assert action["parameters"] == [{"key": "env", "value": "prod"}]
    assert (
        widgets[2]["buttonList"]["buttons"][1]["onClick"]["action"]["function"]
        == "deploy.cancel"
    )
