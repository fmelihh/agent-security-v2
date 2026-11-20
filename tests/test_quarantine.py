"""Layer 1 against the real local model. Run with `make test-model`.

The quarantine is probabilistic, so these tests check what the schema guarantees:
whatever the model writes, the result is a valid request that names no foreign order.
"""

from __future__ import annotations

import pytest

from executor import data
from executor.quarantine import TicketRequest, extract_note, extract_ticket
from executor.session import Session
from lab.examples import EXAMPLES

pytestmark = pytest.mark.model


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["key"] for e in EXAMPLES])
def test_every_example_ticket_becomes_a_valid_request(real_llm, example):
    session = Session(id="t", customer_id=example["customer_id"])
    request = extract_ticket(real_llm, session, example["ticket"])
    print(f"\n  {example['key']}: {request.model_dump()}")
    assert isinstance(request, TicketRequest)
    if request.order_id is not None:
        assert data.ORDERS[request.order_id]["customer_id"] == session.customer_id


def test_poisoned_note_comes_back_as_facts_only(real_llm):
    facts = extract_note(real_llm, data.ORDER_NOTES["A-1001"])
    print(f"\n  A-1001 note: {facts.model_dump()}")
    assert set(facts.model_dump()) == {"carrier_delay", "eta_days"}
