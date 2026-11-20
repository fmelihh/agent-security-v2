"""The executor's data: v1's customers and notes, plus orders with totals.

v1 has no order table, so the refund cap had nothing to read. Totals are example values.
"""

from __future__ import annotations

from lab.data import COMPANY_DOMAINS, CUSTOMERS, KNOWLEDGE_BASE, ORDER_NOTES

__all__ = ["COMPANY_DOMAINS", "CUSTOMERS", "CUSTOMERS_BY_ID", "KNOWLEDGE_BASE", "ORDERS",
           "ORDER_NOTES"]

CUSTOMERS_BY_ID: dict[int, dict] = {c["id"]: c for c in CUSTOMERS}

# Each customer's last_order (A-1001 .. A-1012) belongs to that customer.
ORDERS: dict[str, dict] = {
    c["last_order"]: {"customer_id": c["id"], "total": 59.90, "status": "shipped"}
    for c in CUSTOMERS
}
ORDERS["A-1003"]["status"] = "awaiting_stock"
