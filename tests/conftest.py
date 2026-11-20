"""Shared fixtures: a fake quarantine model and an executor client.

The offline tests never call a model. ``FakeLLM`` stands in for the quarantine model:
it returns whatever the test hands it, shaped into the schema the code asks for.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from executor.app import create_app
from lab.agent import BASE_URL


class FakeLLM:
    """Answers ``with_structured_output(schema).invoke(...)`` with a canned dict."""

    def __init__(self, answer: dict | Exception | None = None):
        self.answer = answer if answer is not None else {"intent": "other"}
        self.seen: list[str] = []

    def with_structured_output(self, schema, **_kwargs):
        fake = self

        class _Bound:
            def invoke(self, messages):
                fake.seen.append(messages[-1].content)
                if isinstance(fake.answer, Exception):
                    raise fake.answer
                return schema(**fake.answer)

        return _Bound()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(fake_llm) -> TestClient:
    return TestClient(create_app(fake_llm))


def model_runner_up() -> bool:
    try:
        return httpx.get(f"{BASE_URL}/models", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture
def real_llm():
    if not model_runner_up():
        pytest.skip("Docker Model Runner is not reachable; run `make model` first")
    from lab.agent import build_llm

    return build_llm()
