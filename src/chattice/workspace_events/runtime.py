"""Independent runtime for asynchronous Workspace resource events."""

from __future__ import annotations

import inspect
import types
from collections.abc import (
    Awaitable,
    Callable,
    Iterator,
    Mapping,
    MutableMapping,
)
from dataclasses import dataclass, field
from functools import cache
from typing import Any, TypeAlias, Union, get_args, get_origin, get_type_hints

from chattice.exceptions import (
    ContextConflictError,
    DependencyResolutionError,
    FilterError,
    InvalidHandlerError,
    RouterConfigurationError,
    SkipHandler,
    StopPropagation,
)
from chattice.filters import F

from .parser import WorkspaceEvent

WorkspaceHandlerCallback: TypeAlias = Callable[..., object]
WorkspaceFilter: TypeAlias = Callable[..., Awaitable[object]]
EventsNextHandler: TypeAlias = Callable[
    [WorkspaceEvent, MutableMapping[str, object]], Awaitable[object]
]
EventsMiddleware: TypeAlias = Callable[
    [EventsNextHandler, WorkspaceEvent, MutableMapping[str, object]],
    Awaitable[object],
]


@dataclass(frozen=True, slots=True)
class _ParameterPlan:
    name: str
    event_types: tuple[type[WorkspaceEvent], ...]
    event_alias: bool
    has_default: bool


@dataclass(frozen=True, slots=True)
class _HandlerPlan:
    callback: WorkspaceHandlerCallback
    parameters: tuple[_ParameterPlan, ...]

    async def invoke(self, event: WorkspaceEvent, data: Mapping[str, object]) -> object:
        kwargs: dict[str, object] = {}
        for parameter in self.parameters:
            if parameter.event_types:
                if not isinstance(event, parameter.event_types):
                    raise DependencyResolutionError(
                        f"Handler {self.callback!r} parameter {parameter.name!r} "
                        f"requires WorkspaceEvent, received {type(event).__name__}"
                    )
                kwargs[parameter.name] = event
            elif parameter.event_alias:
                kwargs[parameter.name] = event
            elif parameter.name in data:
                kwargs[parameter.name] = data[parameter.name]
            elif not parameter.has_default:
                raise DependencyResolutionError(
                    f"Missing required dependency {parameter.name!r} for "
                    f"handler {self.callback!r}"
                )

        result = self.callback(**kwargs)
        if not inspect.isawaitable(result):
            raise InvalidHandlerError(
                f"Handler {self.callback!r} returned a non-awaitable value"
            )
        return await result


def _workspace_event_types(
    annotation: object,
) -> tuple[type[WorkspaceEvent], ...]:
    if annotation is inspect.Signature.empty or annotation is Any:
        return ()
    origin = get_origin(annotation)
    if origin in (types.UnionType, Union):
        result: list[type[WorkspaceEvent]] = []
        for argument in get_args(annotation):
            result.extend(_workspace_event_types(argument))
        return tuple(dict.fromkeys(result))
    if isinstance(annotation, type) and issubclass(annotation, WorkspaceEvent):
        return (annotation,)
    return ()


@cache
def _build_handler_plan(callback: WorkspaceHandlerCallback) -> _HandlerPlan:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError) as error:
        raise InvalidHandlerError(f"Cannot inspect handler {callback!r}") from error
    try:
        hints = get_type_hints(callback)
    except (NameError, TypeError):
        hints = {}

    parameters: list[_ParameterPlan] = []
    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise InvalidHandlerError(
                f"Handler {callback!r} parameter {parameter.name!r} uses unsupported "
                f"kind {parameter.kind.description}"
            )
        annotation = hints.get(parameter.name, parameter.annotation)
        event_types = _workspace_event_types(annotation)
        parameters.append(
            _ParameterPlan(
                name=parameter.name,
                event_types=event_types,
                event_alias=(
                    not event_types
                    and annotation in (inspect.Signature.empty, Any)
                    and parameter.name in {"event", "workspace_event"}
                ),
                has_default=parameter.default is not inspect.Signature.empty,
            )
        )
    return _HandlerPlan(callback=callback, parameters=tuple(parameters))


@dataclass(frozen=True, slots=True)
class _HandlerObject:
    callback: WorkspaceHandlerCallback
    filters: tuple[WorkspaceFilter, ...]
    plan: _HandlerPlan = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            plan = _build_handler_plan(self.callback)
        except TypeError as error:
            raise InvalidHandlerError(
                "Handlers must be hashable so their plans can be cached"
            ) from error
        object.__setattr__(self, "plan", plan)


class _WorkspaceEventObserver:
    def __init__(self) -> None:
        self._handlers: list[_HandlerObject] = []

    @property
    def handlers(self) -> tuple[_HandlerObject, ...]:
        return tuple(self._handlers)

    def register(
        self, callback: WorkspaceHandlerCallback, *filters: WorkspaceFilter | str
    ) -> WorkspaceHandlerCallback:
        normalized = tuple(self._normalize_filter(value) for value in filters)
        self._handlers.append(_HandlerObject(callback=callback, filters=normalized))
        return callback

    def __call__(
        self, *filters: WorkspaceFilter | str
    ) -> Callable[[WorkspaceHandlerCallback], WorkspaceHandlerCallback]:
        def decorator(callback: WorkspaceHandlerCallback) -> WorkspaceHandlerCallback:
            return self.register(callback, *filters)

        return decorator

    @staticmethod
    def _normalize_filter(value: WorkspaceFilter | str) -> WorkspaceFilter:
        if isinstance(value, str):
            return F.cloud_type == value
        if not callable(value):
            raise TypeError("Workspace event filters must be asynchronous callables")
        return value


class _EventsMiddlewareManager:
    def __init__(self) -> None:
        self._items: list[EventsMiddleware] = []

    def register(self, middleware: EventsMiddleware) -> EventsMiddleware:
        if not callable(middleware):
            raise TypeError("Middleware must be callable")
        self._items.append(middleware)
        return middleware

    def __call__(self, middleware: EventsMiddleware) -> EventsMiddleware:
        return self.register(middleware)

    def __iter__(self) -> Iterator[EventsMiddleware]:
        return iter(tuple(self._items))


class EventsRouter:
    """Router tree dedicated to Workspace resource-change events."""

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or "events_router"
        if not self.name.strip():
            raise ValueError("EventsRouter name cannot be empty")
        self.workspace_event = _WorkspaceEventObserver()
        self.middleware = _EventsMiddlewareManager()
        self._parent: EventsRouter | None = None
        self._children: list[EventsRouter] = []
        self._is_dispatcher = False

    @property
    def parent(self) -> EventsRouter | None:
        return self._parent

    @property
    def children(self) -> tuple[EventsRouter, ...]:
        return tuple(self._children)

    def include_router(self, router: EventsRouter) -> EventsRouter:
        if not isinstance(router, EventsRouter):
            raise TypeError("include_router() requires an EventsRouter")
        if router is self:
            raise RouterConfigurationError("An EventsRouter cannot include itself")
        if router._is_dispatcher:
            raise RouterConfigurationError(
                "An EventsDispatcher cannot be attached as a child"
            )
        if router._parent is not None:
            raise RouterConfigurationError(
                f"EventsRouter {router.name!r} is already attached to "
                f"{router._parent.name!r}"
            )
        if router._contains(self):
            raise RouterConfigurationError(
                f"Including {router.name!r} in {self.name!r} would create a cycle"
            )
        router._parent = self
        self._children.append(router)
        return router

    def _contains(self, candidate: EventsRouter) -> bool:
        return self is candidate or any(
            child._contains(candidate) for child in self._children
        )

    def _walk(
        self, inherited: tuple[EventsMiddleware, ...] = ()
    ) -> Iterator[tuple[EventsRouter, tuple[EventsMiddleware, ...]]]:
        middleware = (*inherited, *tuple(self.middleware))
        yield self, middleware
        for child in tuple(self._children):
            yield from child._walk(middleware)


class EventsDispatcher(EventsRouter):
    """Independent feed for Workspace Events; never accepts interactions."""

    def __init__(self, *, name: str = "events_dispatcher") -> None:
        super().__init__(name=name)
        self._is_dispatcher = True

    async def feed_event(self, event: WorkspaceEvent, **context: object) -> object:
        if not isinstance(event, WorkspaceEvent):
            raise TypeError("feed_event() accepts WorkspaceEvent instances only")
        for router, middleware in self._walk():
            for handler in router.workspace_event.handlers:
                data = dict(context)
                try:
                    if not await _evaluate_filters(handler.filters, event, data):
                        continue
                    return await _invoke(handler, middleware, event, data)
                except SkipHandler:
                    continue
                except StopPropagation:
                    return None
        return None


async def _evaluate_filters(
    filters: tuple[WorkspaceFilter, ...],
    event: WorkspaceEvent,
    data: MutableMapping[str, object],
) -> bool:
    for filter_ in filters:
        result = await filter_(event, data)
        if isinstance(result, bool):
            if not result:
                return False
            continue
        if not isinstance(result, Mapping):
            raise FilterError(
                f"Filter {filter_!r} returned {type(result).__name__}; "
                "expected bool or mapping"
            )
        for key, value in result.items():
            if not isinstance(key, str):
                raise FilterError("Filter context keys must be strings")
            if key in data:
                raise ContextConflictError(
                    f"Filter {filter_!r} attempted to redefine context key {key!r}"
                )
            data[key] = value
    return True


async def _invoke(
    handler: _HandlerObject,
    middleware: tuple[EventsMiddleware, ...],
    event: WorkspaceEvent,
    data: MutableMapping[str, object],
) -> object:
    async def resolved_handler(
        resolved_event: WorkspaceEvent,
        resolved_data: MutableMapping[str, object],
    ) -> object:
        return await handler.plan.invoke(resolved_event, resolved_data)

    current: EventsNextHandler = resolved_handler
    for item in reversed(middleware):
        next_handler = current

        async def wrapped(
            wrapped_event: WorkspaceEvent,
            wrapped_data: MutableMapping[str, object],
            *,
            _middleware: EventsMiddleware = item,
            _next: EventsNextHandler = next_handler,
        ) -> object:
            return await _middleware(_next, wrapped_event, wrapped_data)

        current = wrapped
    return await current(event, data)


__all__ = ["EventsDispatcher", "EventsRouter"]
