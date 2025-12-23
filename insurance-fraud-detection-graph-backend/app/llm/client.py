from typing import Any, Optional
from google import genai
from google.genai import types
from app.config import settings
from app.llm.pricing import estimate_cost

_client: Optional[genai.Client] = None

def get_client() -> genai.Client:
    """
    Singleton Google GenAI client with explicit credentials.
    - Developer API (default): api_key + vertexai=False
    - Vertex AI (opt-in): vertexai=True + project + location (use ADC/SA)
    """
    global _client
    if _client:
        return _client

    if settings.USE_VERTEXAI:
        _client = genai.Client(
            vertexai=True,
            project=settings.VERTEX_PROJECT,
            location=settings.VERTEX_LOCATION,
        )
    else:
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            vertexai=False,
        )
    return _client


def _count_tokens(parts: list[types.Part] | None = None, text: str | None = None) -> int | None:
    try:
        if text is not None:
            c = get_client().models.count_tokens(
                model=settings.GENAI_MODEL,
                contents=[types.Part.from_text(text=text)],
            )
        else:
            c = get_client().models.count_tokens(
                model=settings.GENAI_MODEL,
                contents=parts or [],
            )
        return getattr(c, "total_tokens", None)
    except Exception:
        return None


def call_model(
    parts: list[types.Part],
    response_schema: Any = None,
    model: str | None = None,
    max_output_tokens: int | None = None,
    response_mime_type: str = "application/json",
    temperature: float = 0.0,
):
    """
    One-shot helper:
      - calls generate_content()
      - returns (text, input_tokens, output_tokens, cost_estimate)
    """
    model = model or settings.GENAI_MODEL
    max_output_tokens = max_output_tokens or settings.MAX_OUTPUT_TOKENS

    cfg_kwargs = dict(
        temperature=temperature,
        response_mime_type=response_mime_type,
        max_output_tokens=max_output_tokens,
    )
    if response_schema is not None:
        cfg_kwargs["response_schema"] = response_schema

    cfg = types.GenerateContentConfig(**cfg_kwargs)

    resp = get_client().models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=cfg,
    )

    # --- Robust text extraction (some SDKs don't fill .text for JSON) ---
    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        try:
            cands = getattr(resp, "candidates", None) or []
            if cands and getattr(cands[0], "content", None):
                parts_out = getattr(cands[0].content, "parts", None) or []
                # pick first textual part
                for p in parts_out:
                    # Part may have .text or inline bytes; we only want text
                    if getattr(p, "text", None):
                        text = p.text.strip()
                        break
        except Exception:
            text = ""

    usage = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage, "input_tokens", None) if usage else None
    out_tok = getattr(usage, "output_tokens", None) if usage else None

    # Fallbacks if SDK doesn’t return usage
    if in_tok is None:
        in_tok = _count_tokens(parts=parts) or 0
    if out_tok is None:
        out_tok = _count_tokens(text=text) or 0

    cost = estimate_cost(in_tok, out_tok, settings.PRICING_INPUT_PER_M, settings.PRICING_OUTPUT_PER_M)
    return text, in_tok, out_tok, cost