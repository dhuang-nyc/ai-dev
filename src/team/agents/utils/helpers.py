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


# ---------------------------------------------------------------------------
# Token-aware history trimming
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN = 4  # conservative estimate for English text


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _message_tokens(msg: dict) -> int:
    content = msg.get("content", "")
    if isinstance(content, str):
        return _estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += _estimate_tokens(str(block))
            else:
                total += _estimate_tokens(str(block))
        return total
    return _estimate_tokens(str(content))


def trim_history(
    messages: list[dict],
    max_tokens: int = 30_000,
    keep_recent: int = 6,
) -> list[dict]:
    """
    Trim conversation history to fit within a token budget.

    Strategy:
    - Always keep the first message (original project context/idea).
    - Always keep the last `keep_recent` messages (recent context).
    - Drop oldest middle messages until under budget.
    - If still over, summarize dropped messages with a placeholder.
    """
    if not messages:
        return messages

    total = sum(_message_tokens(m) for m in messages)
    if total <= max_tokens:
        return messages

    first = messages[:1]
    tail = messages[-keep_recent:] if len(messages) > keep_recent else messages[1:]
    middle = messages[1:-keep_recent] if len(messages) > keep_recent + 1 else []

    kept_middle = []
    budget = max_tokens - sum(_message_tokens(m) for m in first + tail)
    dropped_count = 0

    for msg in reversed(middle):
        cost = _message_tokens(msg)
        if budget >= cost:
            kept_middle.insert(0, msg)
            budget -= cost
        else:
            dropped_count += 1

    result = first[:]
    if dropped_count > 0:
        result.append({
            "role": "user",
            "content": f"[{dropped_count} earlier message(s) trimmed for context window efficiency. "
            "Key decisions are reflected in the current tech spec and task list.]",
        })
    result.extend(kept_middle)
    result.extend(tail)

    return result
