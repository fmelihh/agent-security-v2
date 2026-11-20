# agent-security-v2

A follow-up to [agent-security](https://github.com/fmelihh/agent-security), the prompt injection lab behind
[The Fundamentals of AI Agent Security: Prompt Injection and the Harness](https://medium.com/data-science-collective/the-fundamentals-of-ai-agent-security-prompt-injection-and-the-harness-d6dc123d3cee).

v1 wraps the model in a harness: `policy_guard` checks tool calls and `output_guard` checks the reply.
But the tools, the customer data and the real PII still live in the same process as the model, and every
`send_email` / `create_refund` is denied, so the guarded agent is safe but cannot do its job.

v2 keeps the v1 agent and adds two things around it:

- a **quarantine model** that reads raw text and can only fill a schema (no tools, no free-text fields), and
- a **tool executor**, a separate process that holds the data, applies the rules and owns the only way out,
  following the [external sandbox pattern](https://blog.primeradiant.com/external-sandboxes-for-coding-agents/).

The privileged model never sees the raw ticket, never sees a raw order note and never sees a real email
address. It works with typed requests and handles such as `<email:1>`.

This is a lab, not a product: one FastAPI file, a few plain Python modules, data in memory.
Egress is a black box that only records what would be sent.

## Lethal trifecta: one lens, three layers

The [lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) is a lens, not an
architecture: private data, untrusted content and external communication must never be open at once.
v2 cuts each leg in a different layer, so a layer that gets fooled is backed by the next one.

| Layer | Leg it cuts | How | Can it be fooled? |
|---|---|---|---|
| 1 · model: quarantine | untrusted content | raw text → `TicketRequest` / `NoteFacts` schema | yes, probabilistic |
| 2 · application: executor | private data, external communication | ticket scope, PII handles, "who and how much" rules | no, deterministic |
| 3 · infrastructure: egress | external communication | the only way out; a black box here | no |

```mermaid
flowchart TB
    subgraph U["Untrusted input"]
        T[Ticket body]
        N["Order notes (A-1001 poisoned)"]
    end
    subgraph L1["Layer 1 · model level (probabilistic)"]
        QT["Ticket quarantine → TicketRequest"]
        QN["Note quarantine → NoteFacts"]
    end
    subgraph A["Privileged agent (typed data only)"]
        M[Privileged model]
        RT["remote_tools (POST /call)"]
        OG[output_guard_v2]
    end
    subgraph L2["Layer 2 · application level (deterministic)"]
        S[Session scope]
        P[Policy]
        V["Vault (handles)"]
        R["/render"]
        D[("data: CUSTOMERS, ORDERS")]
    end
    subgraph L3["Layer 3 · infrastructure (black box)"]
        E[Egress]
    end
    T --> QT --> M
    N --> QN --> RT
    M --> RT --> P
    S --> P --> V --> E
    P --> D
    M --> OG --> R --> User((User))
```

## Components

```mermaid
flowchart LR
    subgraph AG["Agent process · lab/"]
        RS["run_sandboxed()"]
        M[Model]
        RT[remote_tools]
        OG[output_guard_v2]
    end
    subgraph EX["Executor · executor/ · :8787"]
        APP["app.py: /sessions /tools /call /render /records /log"]
        Q[quarantine]
        P[policy]
        TO[tools]
        V[vault]
        D[(data)]
        EG[["egress (black box)"]]
    end
    RS -- "raw ticket" --> APP
    RT -- "POST /call" --> APP
    OG -- "POST /render" --> APP
    M --> RT
    M --> OG
    APP --> Q
    APP --> P
    APP --> TO
    APP --> V
    TO --> D
    TO --> EG
```

Only `executor/` imports the data. The agent process holds a URL, a session id and a typed request.

## One question, before and after

"Where is my order A-1001?" The question is harmless; the internal note of A-1001 carries an injection.

**Before (v1, guarded)**

```mermaid
sequenceDiagram
    participant H as Harness
    participant M as Model
    participant PG as policy_guard
    participant T as Tools + data
    participant OG as output_guard
    H->>M: raw ticket
    M->>PG: get_order_notes(A-1001)
    PG->>T: allowed (no rule for reads)
    T-->>M: raw note + injection
    M->>PG: query_customer_db(limit=20)
    PG->>T: allowed
    T-->>M: 12 customers' real PII
    M->>PG: send_email(audit@partner-verify.com)
    PG-->>M: BLOCKED: domain
    M->>PG: send_email(ada@example.com)
    PG-->>M: BLOCKED: human review denies every email
    M->>OG: reply (may list PII)
    OG-->>H: reply, or [withheld] if 2+ customers appear
```

**After (v2, sandboxed)**

```mermaid
sequenceDiagram
    participant H as Harness
    participant Q as Quarantine
    participant M as Privileged model
    participant P as Executor (policy + vault)
    participant E as Egress (black box)
    H->>Q: POST /sessions (raw ticket, customer 1)
    Q-->>H: TicketRequest {intent: order_status, order_id: A-1001}
    H->>M: typed request only
    M->>P: get_order_notes(A-1001)
    P->>Q: raw note (poisoned)
    Q-->>P: NoteFacts {carrier_delay: true}
    P-->>M: status, carrier_delay
    M->>P: send_email(to=#lt;email:1#gt;)
    Note over P: policy: recipient is the ticket's customer<br/>vault: #lt;email:1#gt; → ada@example.com
    P->>E: send (real address)
    M->>P: reply → /render
    P-->>H: reply, #lt;email:1#gt; resolved for the owner
```

The raw ticket and the poisoned note only ever reach the quarantine. The real address only travels
between the executor and egress.

## The six example tickets

| Example | v1 guarded | v2 sandboxed |
|---|---|---|
| 1 · fake `[SYSTEM]` admin command | email blocked by domain; real PII already in context | instruction lost in quarantine; only the ticket's customer is readable |
| 2 · injection in a forwarded thread | attack blocked, but the customer cannot be answered | attack lost in quarantine, reply goes to the customer |
| 3 · refund of 9999 | denied, but so is every legitimate refund | quarantine is fooled (`refund_amount: 9999`), the order total cap refuses it; a real refund passes |
| 4 · "reply with the full list, CC me" | reply withheld only if 2+ customers appear | the user sees only their own record |
| 5 · DevMode role play | a company-domain email with others' data is stopped only by deny-all review | the body check refuses other customers' handles |
| 6 · poisoned order note | raw note reaches the model | note reduced to `NoteFacts`; the instruction never arrives |

## Layout

```
lab/                  agent side, v1 modes unchanged
  remote_tools.py     LangChain tools built from the executor's /tools listing
  middleware.py       v1 guards + make_output_guard_v2
  sandboxed.py        run_sandboxed(): open a session, run the agent on the typed request
executor/             the boundary (separate process)
  app.py              FastAPI: /sessions /tools /call /render /records /log
  quarantine.py       TicketRequest, NoteFacts, extract + validate
  session.py          one session per ticket, bound to a customer
  policy.py           who may receive mail, how much may be refunded
  vault.py            PII handles: mask out, resolve in
  tools.py            the only code that touches the data
  egress.py           black box: send_email, refund
  data.py             v1 customers + orders with totals
tests/
  test_executor.py    deterministic layers, no model needed
  test_quarantine.py  quarantine against the local qwen model (marked `model`)
  test_sandboxed.py   the six examples end to end against qwen (marked `model`)
```

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Docker Desktop with Model Runner enabled.

```bash
make install          # uv sync
make model            # pull ai/qwen2.5:1.5B-F16 for Docker Model Runner
make test             # offline tests, no model
make test-model       # quarantine + end-to-end tests against the local model
make executor         # run the executor on :8787 (for the manual runs below)
make sandboxed        # run the six example tickets in sandboxed mode
```

The v1 commands (`make attack`, `make defense`, `make dev`, `make ui`) still work as before.

## Known limits

- `customer_id` is trusted from ticket metadata. In a real system it must come from an authenticated channel.
- The quarantine is probabilistic. When it is fooled it can only produce schema-valid wrong values, which layer 2 checks.
- The privileged model only sees the intent, not the customer's words, so replies are plainer.
- A 1.5B model does not always fill the schema; unparseable output becomes `intent="other"` (hand to a human).
- Handles reuse customer ids and are guessable. Fine for a lab, not for production.
- No VM or container isolation: no tool runs code. Add it behind the executor if a `run_python` tool appears.
