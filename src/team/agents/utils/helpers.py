from decimal import Decimal

MODEL_PRICING = {
    "claude-opus-4-6": {
        "input": Decimal("15") / Decimal("1000000"),
        "output": Decimal("75") / Decimal("1000000"),
    },
    "claude-sonnet-4-6": {
        "input": Decimal("3") / Decimal("1000000"),
        "output": Decimal("15") / Decimal("1000000"),
    },
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    pricing = MODEL_PRICING.get(
        model, {"input": Decimal("0"), "output": Decimal("0")}
    )
    return input_tokens * pricing["input"] + output_tokens * pricing["output"]
