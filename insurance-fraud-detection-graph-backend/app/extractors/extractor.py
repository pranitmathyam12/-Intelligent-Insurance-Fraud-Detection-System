from typing import Any, Tuple
import json
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.claim_types.registry import load_resources
from app.llm.client import call_model, get_client
from app.llm.pricing import UsageCost

def _schema_to_genai(model_cls: type[BaseModel]) -> types.Schema:
    """Pydantic JSON schema → google.genai.types.Schema (minimal mapper)."""
    js = model_cls.model_json_schema()

    def build(node: dict) -> types.Schema:
        t = node.get("type")
        if t == "object":
            props = {}
            for k, v in (node.get("properties") or {}).items():
                props[k] = build(v)
            return types.Schema(type=types.Type.OBJECT, properties=props, required=node.get("required"))
        if t == "array":
            return types.Schema(type=types.Type.ARRAY, items=build(node.get("items", {"type": "string"})))
        if t == "boolean": return types.Schema(type=types.Type.BOOLEAN)
        if t == "number":  return types.Schema(type=types.Type.NUMBER)
        return types.Schema(type=types.Type.STRING)

    return build(js)

def _trim_to_json(text: str) -> str:
    if text.startswith("{"):
        return text
    lb, rb = text.find("{"), text.rfind("}")
    return text[lb:rb+1] if (lb != -1 and rb != -1 and rb > lb) else text

def extract(doc_type: str, pdf_bytes: bytes) -> Tuple[dict, int, int, UsageCost | None, bool]:
    """
    Common extractor for all claim types.
    Returns: (payload, input_tokens, output_tokens, cost, ok)
    """
    # Load per-type schema + prompt
    schema_cls, prompt_text = load_resources(doc_type)

    # Build model input parts
    parts = [
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        types.Part.from_text(text=prompt_text),
    ]

    # Try passing Pydantic class directly; else pass converted types.Schema
    try:
        # probe
        _ = types.GenerateContentConfig(response_schema=schema_cls)
        response_schema: Any = schema_cls
    except Exception:
        response_schema = _schema_to_genai(schema_cls)

    # First pass
    text, in_t, out_t, cost = call_model(
        parts=parts,
        response_schema=response_schema,
        model=settings.GENAI_MODEL,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )
    text = _trim_to_json(text)

    try:
        obj = schema_cls.model_validate_json(text)
        payload = obj.model_dump(by_alias=True)
        return payload, in_t, out_t, cost, True
    except ValidationError:
        # Tiny repair pass
        fix_instr = "Return STRICT valid JSON only. No prose."
        parts_fix = [
            types.Part.from_text(text=fix_instr),
            types.Part.from_text(text=text),
        ]
        text2, in2, out2, cost2 = call_model(
            parts=parts_fix,
            response_schema=response_schema,
            model=settings.GENAI_MODEL,
            max_output_tokens=2048,
        )
        text2 = _trim_to_json(text2)
        obj = schema_cls.model_validate_json(text2)
        payload = obj.model_dump(by_alias=True)

        # Merge usage
        in_t += in2
        out_t += out2
        if cost and cost2:
            cost.total_cost_usd = round(cost.total_cost_usd + cost2.total_cost_usd, 6)

        return payload, in_t, out_t, cost, True