import structlog
from dataclasses import dataclass
from app.llm.pricing import UsageCost

log = structlog.get_logger()

@dataclass
class LlmUsage:
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: UsageCost | None

def record_usage(req_id: str, usage: LlmUsage, doc_type: str, ok: bool):
    log.info("llm.usage",
             req_id=req_id,
             model=usage.model,
             doc_type=doc_type,
             input_tokens=usage.input_tokens,
             output_tokens=usage.output_tokens,
             total_tokens=usage.total_tokens,
             cost_total_usd=getattr(usage.cost, "total_cost_usd", None),
             ok=ok)