"""Layer 2 rules: who may receive mail and how much may be refunded.

v1 asked "is this domain allowed?" and then denied every write. These rules ask "is this
the ticket's customer?" and "is this their order, within its total?", so legitimate work
passes and everything else is refused, whatever the model believes.
"""

from __future__ import annotations

from . import data, vault
from .session import Session


def check(session: Session, tool: str, args: dict) -> str | None:
    """None allows the call; a string is the refusal reason."""
    if tool == "send_email":
        return _check_email(session, args)
    if tool == "create_refund":
        return _check_refund(session, args)
    return None


def _check_email(session: Session, args: dict) -> str | None:
    to = str(args.get("to", "")).strip()
    own = to == f"<email:{session.customer_id}>"
    company = "@" in to and to.rsplit("@", 1)[-1].lower() in data.COMPANY_DOMAINS
    if not (own or company):
        return f"recipient {to!r} is neither this ticket's customer nor a company domain"
    text = f"{args.get('subject', '')} {args.get('body', '')}"
    others = vault.foreign_handles(session, text)
    if others:
        return f"the email mentions other customers: {others}"
    if vault.real_pii_in(text):
        return "the email contains raw customer data"
    return None


def _check_refund(session: Session, args: dict) -> str | None:
    order = data.ORDERS.get(str(args.get("order_id", "")))
    if order is None or order["customer_id"] != session.customer_id:
        return "the order does not belong to this ticket's customer"
    try:
        amount = float(args.get("amount"))
    except (TypeError, ValueError):
        return "the refund amount is not a number"
    if not 0 < amount <= order["total"]:
        return f"the refund amount must be above 0 and at most the order total {order['total']}"
    return None
