"""The executor's HTTP API. Run with `make executor` (port 8787).

/sessions  open a session for a ticket; the raw ticket goes to the quarantine, a typed request comes back
/tools     the tool list the agent builds its tools from
/call      run one tool: session -> policy -> tool body -> vault -> egress
/render    check a reply and resolve the owner's handles
/records   what egress recorded
/log       every quarantine result and every call verdict
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lab.agent import build_llm

from . import policy, vault
from .egress import Egress
from .quarantine import extract_ticket
from .session import Session
from .tools import TOOL_SPECS, TOOLS, ToolContext


class OpenRequest(BaseModel):
    customer_id: int
    ticket: str


class CallRequest(BaseModel):
    session: str
    tool: str
    args: dict = {}


class RenderRequest(BaseModel):
    session: str
    text: str


def create_app(llm, egress: Egress | None = None) -> FastAPI:
    """One executor with its own sessions, log and egress; *llm* is the quarantine model."""
    app = FastAPI(title="agent-security executor")
    sessions: dict[str, Session] = {}
    log: list[dict] = []
    out = egress or Egress()

    def session_of(session_id: str) -> Session:
        if session_id not in sessions:
            raise HTTPException(404, "unknown session")
        return sessions[session_id]

    @app.post("/sessions")
    def open_session(req: OpenRequest) -> dict:
        session = Session(id=uuid4().hex[:8], customer_id=req.customer_id)
        sessions[session.id] = session
        request = extract_ticket(llm, session, req.ticket)  # the raw ticket is not kept
        log.append({"session": session.id, "quarantine": request.model_dump()})
        return {"session": session.id, "request": request.model_dump()}

    @app.get("/tools")
    def list_tools() -> list[dict]:
        return TOOL_SPECS

    @app.post("/call")
    def call(req: CallRequest) -> dict:
        session = session_of(req.session)
        if req.tool not in TOOLS:
            raise HTTPException(404, "unknown tool")
        reason = policy.check(session, req.tool, req.args)
        log.append({"session": session.id, "tool": req.tool, "args": req.args,
                    "verdict": "refused" if reason else "allowed", "rule": reason})
        if reason:
            return {"refused": reason}
        try:
            return TOOLS[req.tool](ToolContext(session, llm, out), **req.args)
        except TypeError as exc:  # wrong or missing arguments from the model
            return {"error": f"bad arguments for {req.tool}: {exc}"}

    @app.post("/render")
    def render(req: RenderRequest) -> dict:
        session = session_of(req.session)
        outside = vault.real_pii_in(req.text) + vault.foreign_handles(session, req.text)
        if outside:
            log.append({"session": session.id, "render": "refused", "found": outside})
            return {"refused": f"the reply mentions data outside this ticket: {outside}"}
        return {"text": vault.resolve(session, req.text)}

    @app.get("/records")
    def records() -> dict:
        return {"outbox": out.outbox, "refunds": out.refunds}

    @app.get("/log")
    def read_log() -> list[dict]:
        return log

    return app


# `uvicorn executor.app:app`; building the client does not call the model.
app = create_app(build_llm())
