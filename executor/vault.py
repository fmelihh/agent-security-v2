"""PII handles: the credential-replacement idea applied to customer data.

Results leave the executor with ``<email:1>`` instead of an address. A handle is turned
back into the real value only on the way to egress or to the ticket's owner, and only
when it belongs to the session's customer.
"""

from __future__ import annotations

import re

from . import data
from .session import Session

HANDLE = re.compile(r"<(email|addr):(\d+)>")
_FIELD = {"email": "email", "addr": "address"}
# shortcut: handles reuse customer ids and are guessable; use random per-session ids if handles ever leave the lab.


def mask_customer(customer_id: int) -> dict:
    customer = data.CUSTOMERS_BY_ID[customer_id]
    return {
        "customer": f"cust:{customer_id}",
        "first_name": customer["name"].split()[0],
        "email": f"<email:{customer_id}>",
        "address": f"<addr:{customer_id}>",
        "last_order": customer["last_order"],
    }


def foreign_handles(session: Session, text: str) -> list[str]:
    return [m.group(0) for m in HANDLE.finditer(text) if int(m.group(2)) != session.customer_id]


def real_pii_in(text: str) -> list[str]:
    return [c["email"] for c in data.CUSTOMERS if c["email"] in text or c["address"] in text]


def resolve(session: Session, text: str) -> str:
    customer = data.CUSTOMERS_BY_ID[session.customer_id]

    def swap(match: re.Match) -> str:
        if int(match.group(2)) != session.customer_id:
            return match.group(0)
        return customer[_FIELD[match.group(1)]]

    return HANDLE.sub(swap, text)
