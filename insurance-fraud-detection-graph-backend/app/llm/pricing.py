from dataclasses import dataclass

@dataclass
class UsageCost:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float

def estimate_cost(inp: int, out: int, in_per_m: float, out_per_m: float) -> UsageCost:
    in_cost  = (inp  / 1_000_000) * in_per_m
    out_cost = (out / 1_000_000) * out_per_m
    return UsageCost(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp+out,
        input_cost_usd=round(in_cost, 6),
        output_cost_usd=round(out_cost, 6),
        total_cost_usd=round(in_cost+out_cost, 6),
    )