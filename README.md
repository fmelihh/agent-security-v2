# agent-security-v2

A follow-up to [agent-security](https://github.com/fmelihh/agent-security), the prompt injection lab behind
[The Fundamentals of AI Agent Security: Prompt Injection and the Harness](https://medium.com/data-science-collective/the-fundamentals-of-ai-agent-security-prompt-injection-and-the-harness-d6dc123d3cee).

v1 puts the harness around the model: `policy_guard` checks tool calls, `output_guard` checks the reply.
But the tools, the customer data and the real PII still live in the same process as the model.
v2 applies the [external sandbox pattern](https://blog.primeradiant.com/external-sandboxes-for-coding-agents/):
the agent stays outside, and the tools, data and outbound actions sit behind a separate **tool executor**.

> Status: design only. Nothing is implemented yet. See [Phases](#phases).

## Architecture

```
            agent process (no data, no secrets)             tool executor (separate process)
 ticket ──► model ──► policy_guard ──► remote tool ──HTTP──► session scope ─► policy ─► PII vault ─► egress
              ▲                                                                                     │
              └──────────── typed result, PII replaced by handles (<email:1>) ◄─────────────────────┘
 reply ◄── output_guard (no real PII, no foreign handles) ◄── model
```

| External sandbox idea | v1 today | v2 |
|---|---|---|
| Agent outside, commands over a localhost API | Tools are Python functions in the agent process | Tools are thin HTTP clients of the executor |
| Only mounted folders are visible | `query_customer_db(limit)` returns any rows | Executor binds the ticket's customer; one row, no `limit` |
| Proxy: host + method allow-list | Domain check inside `policy_guard` | Same rules in `executor/policy.json`, enforced again at egress |
| Credential replacement | Real PII enters the model context | PII handles; the executor swaps in real values at send time |
| `--no-builtin-tools` fails closed | No middleware means no protection | Executor unreachable means the tool errors, no fallback |
| Web UI with request log | `print_trace` | `GET /log`: every call, rule and verdict |

## One ticket, step by step

1. The harness opens a session: `POST /sessions {customer_id}`. The customer comes from ticket metadata, never from the model.
2. The model calls tools; each call is `POST /call {session, tool, args}`.
3. The executor returns typed fields only. Emails and addresses come back as handles (`<email:1>`); free-text order notes are withheld.
4. `send_email` / `create_refund` are checked against `policy.json`: recipient must be the session customer or a company domain; a refund must be for the customer's own order and at most its total.
5. The egress step resolves handles to real values and records the action.
6. `output_guard` blocks a reply that holds real PII or a handle from another session; the rest is rendered for the ticket owner.

## Layout (planned)

```
lab/                 agent side; v1 modes stay as they are
  remote_tools.py    HTTP tools built from the executor's /tools listing
  middleware.py      policy_guard reads policy.json; output_guard v2
executor/            the boundary
  app.py             FastAPI: /sessions /tools /call /render /records /log
  scope.py           ticket -> customer_id, order_ids
  vault.py           handle <-> real value, per session
  policy.py          applies policy.json
  tools.py           the only code that touches the data
  policy.json
```

A sixth mode, `sandboxed`, joins `vulnerable | least_privilege | guarded | dual_llm | output_guard`,
so the comparison still changes one variable at a time.

## Phases

| Phase | Scope | Check |
|---|---|---|
| F1 | `scope.py`, `vault.py`, `policy.py` as pure functions; tickets get `customer_id` | offline smoke checks, no model |
| F2 | `executor/app.py`, `lab/remote_tools.py`, `make executor` | tool call works; executor down means the tool fails closed |
| F3 | `sandboxed` mode in defense, graph, serve; `output_guard` v2; report reads `/records` | `make attack` and `make defense` over the six example tickets |
| F4 | `/log` page and live policy edit (optional) | decisions visible in the browser |
| F5 | README and article section "Defense 6" | |

Out of scope for now: VM or WebAssembly isolation. The lab has no tool that runs code; add it when a `run_python` tool appears.
