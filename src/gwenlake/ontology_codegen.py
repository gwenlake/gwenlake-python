import json
import keyword
import re
from typing import Any, Dict, List, Optional, Tuple

_SCALARS = {
    "string": "str",
    "integer": "int",
    "long": "int",
    "short": "int",
    "byte": "int",
    "double": "float",
    "float": "float",
    "decimal": "_decimal.Decimal",
    "boolean": "bool",
    "date": "_datetime.date",
    "timestamp": "_datetime.datetime",
}

_DECODERS = {
    "decimal": "_to_decimal",
    "date": "_to_date",
    "timestamp": "_to_datetime",
}

_HELPERS = {
    "_to_decimal": (
        "def _to_decimal(value: _typing.Any) -> _typing.Any:\n"
        "    return _decimal.Decimal(str(value)) if value is not None else None\n"
    ),
    "_to_date": (
        "def _to_date(value: _typing.Any) -> _typing.Any:\n"
        "    if isinstance(value, str):\n"
        "        return _datetime.date.fromisoformat(value[:10])\n"
        "    return value\n"
    ),
    "_to_datetime": (
        "def _to_datetime(value: _typing.Any) -> _typing.Any:\n"
        "    if isinstance(value, str):\n"
        "        return _datetime.datetime.fromisoformat(value)\n"
        "    return value\n"
    ),
}

_ENCODE = (
    "def _encode(value: _typing.Any) -> _typing.Any:\n"
    "    if hasattr(value, \"isoformat\"):\n"
    "        return value.isoformat()\n"
    "    if hasattr(value, \"as_tuple\"):\n"
    "        return str(value)\n"
    "    return value\n"
)

_RESERVED_PARAMETERS = {"self", "propose", "parameters", "_encode"}
_FIELD_RESERVED = ("from_node", "str", "int", "float", "bool")


def _pascal(name: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", name) if p]
    out = "".join(p[0].upper() + p[1:] for p in parts) or "Object"
    return out if not out[0].isdigit() else f"T{out}"


def _unique(name: str, taken: set) -> str:
    while name in taken:
        name = f"{name}_"
    taken.add(name)
    return name


def _ident(name: str, reserved: Tuple[str, ...] = ()) -> str:
    if keyword.iskeyword(name) or name in reserved:
        return f"{name}_"
    return name


def _scalar(data_type: Any) -> str:
    return _SCALARS.get(data_type, "_typing.Any") if isinstance(data_type, str) else "_typing.Any"


def _primary_key_type(object_types: Dict[str, Dict[str, Any]], name: str) -> str:
    object_type = object_types.get(name) or {}
    pk = object_type.get("primary_key")
    prop = (object_type.get("properties") or {}).get(pk) if pk else None
    return _scalar((prop or {}).get("data_type", "string"))


def _parameter_type(object_types: Dict[str, Dict[str, Any]], data_type: Any) -> str:
    if isinstance(data_type, dict):
        if data_type.get("type") == "ontology_object":
            return _primary_key_type(object_types, data_type.get("object_type_api_name", ""))
        return _scalar(data_type.get("type"))
    return _scalar(data_type)


def _properties(spec: Dict[str, Any]) -> List[Tuple[str, str, bool, Optional[str]]]:
    out = []
    for name, prop in (spec.get("properties") or {}).items():
        data_type = (prop or {}).get("data_type", "string")
        if data_type == "timeseries":
            continue
        required = bool((prop or {}).get("required")) and not (prop or {}).get("sensitive")
        out.append((name, _scalar(data_type), required, _DECODERS.get(data_type)))
    required = [p for p in out if p[2]]
    optional = [p for p in out if not p[2]]
    return required + optional


def _annotation(type_name: str, required: bool) -> str:
    return type_name if required else f"{type_name} | None"


def _object_class(cls: str, spec: Dict[str, Any], used: set) -> List[str]:
    props = _properties(spec)
    lines = ["@_dataclass(frozen=True)", f"class {cls}:"]
    for name, type_name, required, _ in props:
        lines.append(f"    {_ident(name, _FIELD_RESERVED)}: {_annotation(type_name, required)}" + ("" if required else " = None"))
    if props:
        lines.append("")
    lines += ["    @classmethod", f"    def from_node(cls, node: dict[str, _typing.Any]) -> {cls}:"]
    if not props:
        lines.append("        return cls()")
    else:
        lines.append("        return cls(")
        for name, _, _, decoder in props:
            value = f"node.get({json.dumps(name)})"
            if decoder:
                used.add(decoder)
                value = f"{decoder}({value})"
            lines.append(f"            {_ident(name, _FIELD_RESERVED)}={value},")
        lines.append("        )")
    return lines


def _protocol(cls: str, spec: Dict[str, Any]) -> List[str]:
    lines = [f"class {cls}(_typing.Protocol):"]
    props = _properties(spec)
    if not props:
        lines.append("    ...")
    for name, type_name, required, _ in props:
        lines += ["    @property", f"    def {_ident(name, _FIELD_RESERVED)}(self) -> {_annotation(type_name, required)}: ..."]
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _object_methods(api_name: str, cls: str, spec: Dict[str, Any], object_types: Dict[str, Dict[str, Any]]) -> List[str]:
    key = json.dumps(api_name)
    lines = [
        f"    def query_{api_name}(",
        "        self,",
        "        *,",
        "        filters: list[dict[str, _typing.Any]] | None = None,",
        "        order_by: list[dict[str, _typing.Any]] | None = None,",
        "        limit: int | None = None,",
        "        offset: int | None = None,",
        f"    ) -> list[{cls}]:",
        "        document = self._client.ontologies.query(",
        f"            self.ontology_id, {key}, filters=filters,",
        "            order_by=order_by, limit=limit, offset=offset,",
        "        )",
        f"        return [{cls}.from_node(node) for node in document.get(\"@graph\") or []]",
    ]
    if spec.get("primary_key"):
        pk_type = _primary_key_type(object_types, api_name)
        lines += [
            "",
            f"    def get_{api_name}(self, primary_key: {pk_type}) -> {cls} | None:",
            "        try:",
            f"            node = self._client.ontologies.object(self.ontology_id, {key}, str(primary_key))",
            "        except httpx.HTTPStatusError as exc:",
            "            if exc.response.status_code == 404:",
            "                return None",
            "            raise",
            f"        return {cls}.from_node(node)",
        ]
    return lines


def _action_methods(api_name: str, spec: Dict[str, Any], object_types: Dict[str, Dict[str, Any]]) -> List[str]:
    key = json.dumps(api_name)
    params = []
    for name, parameter in (spec.get("parameters") or {}).items():
        type_name = _parameter_type(object_types, (parameter or {}).get("data_type"))
        params.append((name, type_name, bool((parameter or {}).get("required"))))
    params = [p for p in params if p[2]] + [p for p in params if not p[2]]
    signature = [
        f"{_ident(name, tuple(_RESERVED_PARAMETERS))}: {_annotation(type_name, required)}" + ("" if required else " = None")
        for name, type_name, required in params
    ]
    body = ["        parameters: dict[str, _typing.Any] = {}"]
    for name, _, required in params:
        local = _ident(name, tuple(_RESERVED_PARAMETERS))
        if required:
            body.append(f"        parameters[{json.dumps(name)}] = _encode({local})")
        else:
            body += [f"        if {local} is not None:", f"            parameters[{json.dumps(name)}] = _encode({local})"]
    out = []
    for verb, extra_sig, call in (
        ("validate", "", f"self._client.ontologies.validate_action(self.ontology_id, {key}, parameters)"),
        ("apply", "propose: bool = False", f"self._client.ontologies.apply_action(self.ontology_id, {key}, parameters, propose=propose)"),
    ):
        head = ["self", "*"] + signature if signature or extra_sig else ["self"]
        lines = [f"    def {verb}_{api_name}({', '.join(head + ([extra_sig] if extra_sig else []))}) -> dict[str, _typing.Any]:"]
        lines += body
        lines.append(f"        return {call}")
        if out:
            out.append("")
        out += lines
    return out


def generate(spec: Dict[str, Any]) -> str:
    object_types = {o["api_name"]: o for o in spec.get("object_types") or []}
    interfaces = [i for i in spec.get("interfaces") or []]
    action_types = [a for a in spec.get("action_types") or []]
    ontology_id = spec.get("id", "")
    used: set = set()

    blocks: List[List[str]] = []
    taken: set = set()
    class_names = {name: _unique(_pascal(name), taken) for name in object_types}
    for name, obj in object_types.items():
        blocks.append(_object_class(class_names[name], obj, used))
    for iface in interfaces:
        blocks.append(_protocol(_unique(_pascal(iface["api_name"]), taken), iface))

    cls_name = _unique(f"{_pascal(spec.get('api_name') or 'ontology')}Ontology", taken)
    client = [
        f"class {cls_name}:",
        f"    ontology_id = {json.dumps(ontology_id)}" if ontology_id else "    ontology_id: str",
        "",
        "    def __init__(self, client: _gwenlake.Gwenlake, ontology_id: str | None = None):",
        "        self._client = client",
        "        if ontology_id is not None:",
        "            self.ontology_id = ontology_id",
    ]
    methods: List[List[str]] = []
    for name, obj in object_types.items():
        methods.append(_object_methods(name, class_names[name], obj, object_types))
    for action in action_types:
        methods.append(_action_methods(action["api_name"], action, object_types))
    for method in methods:
        client += [""] + method
    blocks.append(client)

    body_lines: List[str] = []
    for helper in sorted(used):
        body_lines += _HELPERS[helper].rstrip("\n").split("\n") + ["", ""]
    if action_types:
        body_lines += _ENCODE.rstrip("\n").split("\n") + ["", ""]
    for block in blocks:
        body_lines += block + ["", ""]
    body = "\n".join(body_lines).rstrip("\n") + "\n"

    stdlib = []
    if re.search(r"\b_datetime\.", body):
        stdlib.append("import datetime as _datetime")
    if re.search(r"\b_decimal\.", body):
        stdlib.append("import decimal as _decimal")
    if re.search(r"\b_typing\.", body):
        stdlib.append("import typing as _typing")
    if re.search(r"^@_dataclass", body, re.M):
        stdlib.append("from dataclasses import dataclass as _dataclass")
    third_party = ["import gwenlake as _gwenlake"]
    if re.search(r"\bhttpx\.", body):
        third_party.append("import httpx")
    groups = [["from __future__ import annotations"], stdlib, third_party]
    imports = "\n\n".join("\n".join(g) for g in groups if g)
    return imports + "\n\n\n" + body
