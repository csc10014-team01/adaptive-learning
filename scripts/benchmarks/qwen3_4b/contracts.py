"""Small closed JSON contracts shared by Ollama and the offline validator."""


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def enum(*values):
    return {"type": "string", "enum": list(values)}


PHRASER = obj({"question": {"type": "string", "minLength": 20, "maxLength": 1800}})
PARSER = obj({
    "steps": {"type": "array", "minItems": 1, "maxItems": 10, "items": obj({
        "line": {"type": "integer", "minimum": 1, "maximum": 20},
        "expression": {"type": "string", "maxLength": 100},
        "purpose": enum("count", "exclude", "combine", "conclude", "setup"),
        "reference": {"type": "integer", "minimum": 0, "maximum": 10},
        "flags": {"type": "array", "maxItems": 4, "uniqueItems": True,
                  "items": enum("arithmetic", "formula", "constraint", "incomplete",
                                "ambiguous", "alternative")},
    })},
    "review": {"type": "boolean"},
})


def validate(value, schema, path="$"):
    """Validate exactly the JSON Schema subset used above; reject bool-as-int."""
    kind = schema["type"]
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if type(value) is not types[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: unknown enum value")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError(f"{path}: missing or additional fields")
        for key, child in schema["properties"].items():
            validate(value[key], child, f"{path}.{key}")
    if kind in ("string", "array"):
        low, high = ("minLength", "maxLength") if kind == "string" else ("minItems", "maxItems")
        if len(value) < schema.get(low, 0) or len(value) > schema.get(high, 10**9):
            raise ValueError(f"{path}: length outside bounds")
    if kind == "array":
        if schema.get("uniqueItems") and len(value) != len(set(value)):
            raise ValueError(f"{path}: duplicate items")
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")
    if kind == "integer" and not schema.get("minimum", value) <= value <= schema.get("maximum", value):
        raise ValueError(f"{path}: integer outside bounds")
