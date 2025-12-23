from typing import Optional, Iterable
import json, re, structlog, io
from google.genai import types
from app.llm.client import call_model
from app.config import settings
from pypdf import PdfReader

log = structlog.get_logger()

CLASS_PROMPT_TPL = (
    "Classify this insurance claim PDF into exactly one category. "
    "Allowed categories: {allowed}. "
    "Respond ONLY with JSON of the form: {{\"doc_type\": \"<one-of-allowed>\"}}. "
    "Do not include explanations."
)

def _response_schema_obj(allowed: Iterable[str]):
    allowed_list = list(allowed)
    return types.Schema(
        type=types.Type.OBJECT,
        required=["doc_type"],
        properties={
            "doc_type": types.Schema(
                type=types.Type.STRING,
                enum=allowed_list
            )
        }
    )

def _heuristic_sniff(pdf_bytes: bytes, allowed: set[str]) -> Optional[str]:
    text = ""
    try:
        # Try pypdf first for robust extraction
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text().lower()
    except Exception:
        # Fallback to raw bytes decode if pypdf fails
        try:
            text = pdf_bytes.decode(errors="ignore").lower()
        except Exception:
            text = ""

    # Specific headers for generated PDFs
    if "health" in allowed and "health insurance claim" in text:
        return "health"
    if "life" in allowed and "life insurance claim" in text:
        return "life"
    if "motor" in allowed and "motor vehicle insurance claim" in text:
        return "motor"
    if "mobile" in allowed and "mobile device insurance claim" in text:
        return "mobile"
    if "property" in allowed and "property insurance claim" in text:
        return "property"
    if "travel" in allowed and "travel insurance claim" in text:
        return "travel"

    # Fallback broader keywords
    if "health" in allowed and re.search(r"\bhealth\b|\bmedical\b|\bdiagnosis\b|\bprovider\b", text):
        return "health"
    if "motor" in allowed and re.search(r"\bvehicle\b|\bvin\b|\blicense plate\b|\bauto\b|\baccident\b", text):
        return "motor"
    if "property" in allowed and re.search(r"\bproperty\b|\baddress\b|\bbuilding\b|\bcontents\b|\bfire\b|\bflood\b", text):
        return "property"
    
    return None

def classify(pdf_bytes: bytes, allowed: Iterable[str]) -> Optional[str]:
    allowed_set = set(s.lower() for s in allowed)
    if not allowed_set:
        return None
    if len(allowed_set) == 1:
        # Only one possible answer — just return it
        return next(iter(allowed_set))

    # 0) Heuristic sniff (Prioritized)
    # Check the first 64KB for keywords
    doc_type = _heuristic_sniff(pdf_bytes, allowed_set)
    if doc_type:
        log.info("classifier.heuristic_hit", doc_type=doc_type)
        return doc_type

    prompt = CLASS_PROMPT_TPL.format(allowed=", ".join(sorted(allowed_set)))
    schema = _response_schema_obj(allowed_set)

    # 1) JSON classification
    parts = [
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        types.Part.from_text(text=prompt),
    ]
    text, *_ = call_model(
        parts,
        response_schema=schema,
        model=settings.GENAI_MODEL,
        max_output_tokens=16,
        response_mime_type="application/json",
        temperature=0.0,
    )
    raw = (text or "").strip()
    log.info("classifier.raw", raw=raw)

    doc_type = None
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            value = str(obj.get("doc_type", "")).strip().lower()
            if value in allowed_set:
                doc_type = value
        except Exception:
            doc_type = None

    # 2) Fallback: plain text one-word ask
    if not doc_type:
        fb_prompt = f"One word only from {{{', '.join(sorted(allowed_set))}}}."
        parts_fb = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            types.Part.from_text(text=fb_prompt),
        ]
        text2, *_ = call_model(
            parts_fb,
            response_schema=None,
            model=settings.GENAI_MODEL,
            max_output_tokens=8,
            response_mime_type="text/plain",
            temperature=0.0,
        )
        raw2 = (text2 or "").strip().lower()
        if raw2 in allowed_set:
            doc_type = raw2
        else:
            raw2 = raw2.split()[0] if raw2 else ""
            if raw2 in allowed_set:
                doc_type = raw2

    return doc_type