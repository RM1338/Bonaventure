"""Cooperative decoding budgets; partial output must never be accepted after expiry."""
import math
import time


def generate_with_budget(model, inputs, max_new_tokens, seconds, label):
    budget = float(seconds)
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError(f"{label} generation budget must be positive and finite")
    start = time.monotonic()
    output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, max_time=budget)
    # Transformers checks max_time between steps, not during a forward pass.
    if time.monotonic() - start >= budget:
        raise TimeoutError(f"{label} generation exceeded its budget; partial output discarded")
    return output
