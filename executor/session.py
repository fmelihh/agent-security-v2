"""One session per ticket. Its customer is the scope of every call made in it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    id: str
    # Comes from the harness (ticket metadata), never from a model.
    customer_id: int
