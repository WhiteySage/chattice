"""State and StatesGroup markers."""

from __future__ import annotations

from typing import ClassVar


class State:
    """A named workflow state.

    Members of a StatesGroup get ``<GroupName>:<attr_name>`` string keys;
    standalone states may pass an explicit key.
    """

    def __init__(self, *, state: str | None = None) -> None:
        self._state = state
        self._name: str | None = None
        self._group: str | None = None

    @property
    def state(self) -> str:
        """The string key used by storages and StateFilter."""
        if self._state is not None:
            return self._state
        if self._group is None or self._name is None:
            raise RuntimeError("Unbound State: it must be a StatesGroup member")
        return f"{self._group}:{self._name}"


class StatesGroupMeta(type):
    """Collects State members into an insertion-ordered __all_states__."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        **kwargs: object,
    ) -> StatesGroupMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        states: dict[str, State] = {}
        for base in bases:
            states.update(getattr(base, "__all_states__", {}))
        for attr_name, attr in namespace.items():
            if isinstance(attr, State):
                attr._name = attr_name
                attr._group = name
                states[attr_name] = attr
        # cls is typed as the metaclass; the attribute is set on each class.
        cls.__all_states__ = states  # type: ignore[attr-defined]
        return cls


class StatesGroup(metaclass=StatesGroupMeta):
    """Base class for workflow state groups."""

    __all_states__: ClassVar[dict[str, State]] = {}


__all__ = ["State", "StatesGroup", "StatesGroupMeta"]
