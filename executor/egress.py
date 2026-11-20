"""Layer 3: the only way out, treated as a black box.

In the lab it records what would be sent. A real deployment plugs SMTP or a payment API in
here; nothing else in the executor would change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Egress:
    outbox: list[dict] = field(default_factory=list)
    refunds: list[dict] = field(default_factory=list)

    def send_email(self, to: str, subject: str, body: str) -> None:
        self.outbox.append({"to": to, "subject": subject, "body": body})

    def refund(self, order_id: str, amount: float) -> None:
        self.refunds.append({"order_id": order_id, "amount": amount})
