from __future__ import annotations

from rationalevault.schema.upcaster import UpcasterRegistry, task_created_v1_to_v2
from rationalevault.schema.events import EventType


def test_empty_registry() -> None:
    registry = UpcasterRegistry()
    assert registry.get_upcaster(EventType.TASK_CREATED, 1) is None
    assert registry.is_registered(EventType.TASK_CREATED, 1) is False


def test_init_with_upcasters_dict() -> None:
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    assert registry.is_registered(EventType.TASK_CREATED, 1) is True
    assert registry.get_upcaster(EventType.TASK_CREATED, 1) is task_created_v1_to_v2


def test_is_registered_returns_false_for_missing_version() -> None:
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    assert registry.is_registered(EventType.TASK_CREATED, 2) is False


def test_is_registered_returns_false_for_missing_event_type() -> None:
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    assert registry.is_registered(EventType.PROJECT_CREATED, 1) is False


def test_register_adds_upcaster() -> None:
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)
    assert registry.is_registered(EventType.TASK_CREATED, 1) is True
    assert registry.get_upcaster(EventType.TASK_CREATED, 1) is task_created_v1_to_v2


def test_upcaster_callable_works() -> None:
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    upcaster = registry.get_upcaster(EventType.TASK_CREATED, 1)
    result = upcaster({"title": "test", "description": "desc"})
    assert result == {"details": {"summary": "test", "body": "desc"}}
