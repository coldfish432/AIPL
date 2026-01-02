from __future__ import annotations

from typing import Any


def _validate_object_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    if not isinstance(data, dict):
        return False, "expected object"
    required = schema.get("required", [])
    for key in required:
        if key not in data:
            return False, f"missing required key: {key}"
    props = schema.get("properties", {})
    for key, subschema in props.items():
        if key in data and isinstance(subschema, dict):
            ok, err = validate_schema(data[key], subschema)
            if not ok:
                return False, f"key {key}: {err}"
    return True, None


def _validate_array_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    if not isinstance(data, list):
        return False, "expected array"
    items = schema.get("items")
    if isinstance(items, dict):
        for idx, item in enumerate(data):
            ok, err = validate_schema(item, items)
            if not ok:
                return False, f"item {idx}: {err}"
    return True, None


def _validate_string_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, str) else (False, "expected string")


def _validate_integer_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, int) and not isinstance(data, bool)) else (False, "expected integer")


def _validate_number_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    return (True, None) if (isinstance(data, (int, float)) and not isinstance(data, bool)) else (False, "expected number")


def _validate_boolean_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    return (True, None) if isinstance(data, bool) else (False, "expected boolean")


def _validate_null_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    return (True, None) if data is None else (False, "expected null")


_SCHEMA_VALIDATORS = {
    "object": _validate_object_schema,
    "array": _validate_array_schema,
    "string": _validate_string_schema,
    "integer": _validate_integer_schema,
    "number": _validate_number_schema,
    "boolean": _validate_boolean_schema,
    "null": _validate_null_schema,
}


def validate_schema(data: Any, schema: dict, path: str = "") -> tuple[bool, str | None]:
    any_of = schema.get("anyOf")
    if any_of:
        for sub in any_of:
            ok, _ = validate_schema(data, sub, path)
            if ok:
                return True, None
        return False, f"{path}: no schema matched"

    one_of = schema.get("oneOf")
    if one_of:
        matches = 0
        for sub in one_of:
            ok, _ = validate_schema(data, sub, path)
            if ok:
                matches += 1
        if matches != 1:
            return False, f"{path}: exactly one should match"
        return True, None

    all_of = schema.get("allOf")
    if all_of:
        for sub in all_of:
            ok, err = validate_schema(data, sub, path)
            if not ok:
                return False, err
        return True, None

    stype = schema.get("type")
    validator = _SCHEMA_VALIDATORS.get(stype)
    if validator:
        return validator(data, schema)
    enum = schema.get("enum")
    if enum is not None:
        return (True, None) if data in enum else (False, "expected enum value")
    return True, None
