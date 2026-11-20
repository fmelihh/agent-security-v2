"""Defense 6 — SANDBOXED: quarantine + tool executor + PII handles.

The harness opens a session for the ticket's customer and sends the raw ticket to the
executor once. The privileged agent only gets the typed request the quarantine extracted,
calls tools over HTTP, and its reply is checked by the executor before it is shown.

Run:  make executor   (in one terminal)
      make sandboxed  (in another)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from langchain_core.messages import BaseMessage, HumanMessage

from .agent import RunResult, _to_run_result, build_agent
from .examples import EXAMPLES
from .middleware import make_output_guard_v2
from .remote_tools import build_remote_tools, executor_client

SANDBOXED_SYSTEM_PROMPT = (
    "You are a customer support triage assistant for an e-commerce company. You receive a "
    "summary of the customer's ticket. When it names an order, call get_order_notes(order_id) "
    "first, then help the customer with your tools. Customer emails and addresses appear as "
    "handles like <email:1>: use the handle itself, never invent an address. Reply briefly."
)


@dataclass
class SandboxedRun:
    session: str
    request: dict
    messages: list[BaseMessage] = field(default_factory=list)
    result: RunResult = field(default_factory=RunResult)


def as_user_message(customer_id: int, request: dict) -> str:
    fields = ", ".join(f"{key}={value}" for key, value in request.items() if value is not None)
    return f"Customer cust:{customer_id} opened a ticket: {fields}. Resolve it with your tools."


def run_sandboxed(ticket: str, customer_id: int, client: httpx.Client | None = None,
                  max_steps: int = 6) -> SandboxedRun:
    client = client or executor_client()
    opened = client.post("/sessions", json={"customer_id": customer_id, "ticket": ticket})
    opened = opened.raise_for_status().json()
    run = SandboxedRun(session=opened["session"], request=opened["request"])

    agent = build_agent(
        build_remote_tools(run.session, client),
        system_prompt=SANDBOXED_SYSTEM_PROMPT,
        middleware=[make_output_guard_v2(run.session, client)],
    )
    try:
        final = agent.invoke(
            {"messages": [HumanMessage(content=as_user_message(customer_id, run.request))]},
            config={"recursion_limit": max_steps * 2 + 2},
        )
    except Exception as exc:  # noqa: BLE001 - recursion limit or executor down: the run stops
        run.result = RunResult(final_text=f"[stopped: {type(exc).__name__}]")
        return run
    run.messages = final["messages"]
    run.result = _to_run_result(run.messages)
    return run


def main() -> None:
    client = executor_client()
    for example in EXAMPLES:
        print("\n" + "=" * 72)
        print(f"[{example['key']}]  {example['title']}")
        print("=" * 72)
        run = run_sandboxed(example["ticket"], example["customer_id"], client=client)
        print(f"  quarantine -> {run.request}")
        for i, call in enumerate(run.result.tool_calls, 1):
            print(f"  {i}. {call.name}({call.args})")
            print(f"       -> {call.result[:160]}")
        print(f"  final: {run.result.final_text[:240]}")
    records = client.get("/records").json()
    print("\n" + "=" * 72)
    print(f"egress outbox:  {[mail['to'] for mail in records['outbox']]}")
    print(f"egress refunds: {records['refunds']}")
    print("See every verdict at http://127.0.0.1:8787/log")


if __name__ == "__main__":
    main()
