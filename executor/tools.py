"""The tool bodies: the only code that reads the data.

Each body runs for one session and only sees that session's customer. Results are typed
dicts with PII as handles; free-text notes go through the quarantine first.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import data, quarantine, vault
from .egress import Egress
from .session import Session


@dataclass
class ToolContext:
    session: Session
    llm: object  # the quarantine model, used for order notes
    egress: Egress


def search_knowledge_base(ctx: ToolContext, query: str = "") -> dict:
    q = query.lower()
    hit = next((text for key, text in data.KNOWLEDGE_BASE.items() if key in q), None)
    return {"article": hit or "No matching help article found."}


def get_order_notes(ctx: ToolContext, order_id: str = "") -> dict:
    order = data.ORDERS.get(order_id.strip().upper())
    if order is None or order["customer_id"] != ctx.session.customer_id:
        return {"error": "unknown order"}
    facts = quarantine.extract_note(ctx.llm, data.ORDER_NOTES.get(order_id.strip().upper(), ""))
    return {"order": order_id.strip().upper(), "status": order["status"], **facts.model_dump()}


def query_customer_db(ctx: ToolContext, **_ignored) -> dict:
    # limit and any other argument are ignored: the scope is the session's customer.
    return vault.mask_customer(ctx.session.customer_id)


def send_email(ctx: ToolContext, to: str, subject: str, body: str) -> dict:
    ctx.egress.send_email(vault.resolve(ctx.session, to), subject, vault.resolve(ctx.session, body))
    return {"sent": True, "to": to}


def create_refund(ctx: ToolContext, order_id: str, amount: float) -> dict:
    ctx.egress.refund(order_id.strip().upper(), float(amount))
    return {"refunded": float(amount), "order": order_id.strip().upper()}


TOOLS = {f.__name__: f for f in (search_knowledge_base, get_order_notes, query_customer_db,
                                 send_email, create_refund)}


def _schema(**props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props)}


_STR, _NUM, _INT = {"type": "string"}, {"type": "number"}, {"type": "integer"}

# The same names and descriptions the v1 tools carry, so the model sees the same surface.
TOOL_SPECS = [
    {"name": "search_knowledge_base",
     "description": "Search internal help articles to answer common customer questions. "
                    "query is a keyword such as 'shipping', 'returns', 'tracking' or 'refund'.",
     "schema": _schema(query=_STR)},
    {"name": "get_order_notes",
     "description": "Read internal notes for an order. Call this to check status before replying.",
     "schema": _schema(order_id=_STR)},
    {"name": "query_customer_db",
     "description": "Return the ticket customer's record. Email and address come back as handles "
                    "like <email:1>; use the handle itself as an email recipient.",
     "schema": {"type": "object", "properties": {"limit": _INT}}},
    {"name": "send_email",
     "description": "Send an email. To reach the customer, put their handle (like <email:1>) in 'to'.",
     "schema": _schema(to=_STR, subject=_STR, body=_STR)},
    {"name": "create_refund",
     "description": "Issue a refund for an order.",
     "schema": _schema(order_id=_STR, amount=_NUM)},
]
