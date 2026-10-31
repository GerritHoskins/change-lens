"""Output schemas for the `llm` port and a small validator for the JSON Schema subset they use.

The schemas are written for OpenAI-style `json_schema` strict mode: every object lists all its
properties as required and sets `additionalProperties: false`; optional values are nullable.
No booleans: on IONOS (D-17 probe, 2026-10-31) strict decoding of a boolean let Qwen emit
whitespace until `max_tokens`, so `ChangeFindings` leaves out `material` (D-17 does not score it).
The validator is the second line: output is always validated locally, whatever the provider claims.
Error messages name the path and rule only, never the offending value (AC-23).
"""
from __future__ import annotations

CATEGORIES = ["deliverable", "quantity", "date_deadline", "responsibility_owner", "approval",
              "other_material", "structure"]
CHANGE_TYPES = ["added", "changed", "removed", "not_addressed", "uncertain", "equivalent"]
SCOPES = ["complete", "partial", "unknown"]

_NULLABLE_STR = {"type": ["string", "null"]}

CHANGE_FINDINGS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["newer_scope", "findings"],
    "properties": {
        # Asked first so the model commits to a scope (03 §4.2) before listing omissions.
        "newer_scope": {"type": "string", "enum": SCOPES},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "change_type", "old_value", "new_value",
                             "evidence_old", "evidence_new"],
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "change_type": {"type": "string", "enum": CHANGE_TYPES},
                    "old_value": _NULLABLE_STR,
                    "new_value": _NULLABLE_STR,
                    "evidence_old": _NULLABLE_STR,
                    "evidence_new": _NULLABLE_STR,
                },
            },
        },
    },
}

FACT_TYPES = ["deliverable", "quantity", "date_deadline", "responsibility_owner", "approval",
              "other_material"]
CONFIDENCE = ["high", "medium", "low"]
AMBIGUITY = ["ambiguous_date", "ambiguous_entity", "ambiguous_value", None]

# I-2 extraction, one call per chunk of numbered blocks. `block` is the 1-based block number in
# the chunk; `quote` is copied from that block and located there deterministically (no offsets
# from the model). Ambiguity is an enum rather than a boolean (see the module note).
FACT_LIST = {
    "type": "object",
    "additionalProperties": False,
    "required": ["facts"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "subject", "value", "block", "quote", "ambiguity", "confidence"],
                "properties": {
                    "type": {"type": "string", "enum": FACT_TYPES},
                    "subject": {"type": "string"},
                    "value": _NULLABLE_STR,
                    "block": {"type": "integer"},
                    "quote": {"type": "string"},
                    "ambiguity": {"type": ["string", "null"], "enum": AMBIGUITY},
                    "confidence": {"type": "string", "enum": CONFIDENCE},
                },
            },
        },
    },
}

# I-3 alignment: the model proposes which leftover earlier fact corresponds to which newer fact.
# Indices refer to the numbered lists in the data blocks; the code checks them and never forces a
# match the model is unsure of (AC-7).
FACT_MATCHES = {
    "type": "object",
    "additionalProperties": False,
    "required": ["matches"],
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["earlier", "later", "confidence"],
                "properties": {
                    "earlier": {"type": "integer"},
                    "later": {"type": "integer"},
                    "confidence": {"type": "string", "enum": CONFIDENCE},
                },
            },
        },
    },
}

# I-3 compare, rule 3 (03 §4.1): matched pairs with equal values and qualifiers, judged for meaning.
SAME_MEANING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdicts"],
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pair", "verdict"],
                "properties": {
                    "pair": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["equivalent", "meaning_changed"]},
                },
            },
        },
    },
}

SCHEMAS = {"ChangeFindings": CHANGE_FINDINGS, "FactList": FACT_LIST, "FactMatches": FACT_MATCHES,
           "SameMeaning": SAME_MEANING}

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
          "integer": int, "number": (int, float)}


class SchemaError(ValueError):
    """Content-free: the message is a JSON path and a rule name."""


def _is(value, name: str) -> bool:
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def validate(value, schema: dict, path: str = "$") -> None:
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(_is(value, n) for n in names):
            raise SchemaError(f"{path}: type")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: enum")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}.{key}: required")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    raise SchemaError(f"{path}: additionalProperties")
        for key, sub in props.items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}")
    elif isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")
