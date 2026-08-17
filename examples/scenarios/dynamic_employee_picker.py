"""Dynamic employee picker: UPDATE_WIDGET autocomplete (WIDGET_UPDATED).

The documented Google autocomplete flow: the user types into a
selectionInput, Google sends WIDGET_UPDATED with the query parameter, the
handler answers with WidgetAutocomplete suggestions.

Run:
    python examples/scenarios/dynamic_employee_picker.py
"""

from __future__ import annotations

import asyncio
from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import WidgetUpdatedEvent
from chattice.transports.http import WidgetAutocomplete

EMPLOYEES = ("Иван Иванов", "Иван Петров", "Мария Соколова", "Пётр Сидоров")


async def main() -> None:
    router = Router()

    @router.widget_updated()
    async def autocomplete(event: WidgetUpdatedEvent) -> WidgetAutocomplete:
        query = str(event.parameters.get("autocomplete_widget_query", "")).lower()
        matches = tuple(name for name in EMPLOYEES if query in name.lower())
        return WidgetAutocomplete(widget_id="employee", suggestions=matches)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payload = {
        "type": "WIDGET_UPDATED",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {
            "invokedFunction": "employee.search",
            "parameters": {"autocomplete_widget_query": "иван"},
        },
    }
    event = parse_interaction(payload)
    response = await dispatcher.feed_update(event)
    print("suggestions:", cast(WidgetAutocomplete, response).to_dict())


if __name__ == "__main__":
    asyncio.run(main())
