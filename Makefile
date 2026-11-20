.PHONY: help install model smoke attack defense dev ui test test-model executor sandboxed

help:  ## Show the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  make %-10s %s\n", $$1, $$2}'

install:  ## Install dependencies with uv
	uv sync

model:  ## Start Docker and pull the small local model
	docker desktop start
	docker model pull ai/qwen2.5:1.5B-F16

smoke:  ## Offline sanity checks (no model needed)
	uv run python -m lab.smoke

attack:  ## Run the attack scenario (direct + indirect)
	uv run python -m lab.attack

defense:  ## Run all five defenses
	uv run python -m lab.defense

dev:  ## Drive the agent yourself in LangGraph Studio
	uv run langgraph dev

ui:  ## Run the agent from the LangServe browser playground
	uv run uvicorn lab.serve:app --reload

test:  ## v2 offline tests (no model needed)
	uv run pytest -q

test-model:  ## v2 quarantine + end-to-end tests against the local model
	uv run pytest -q -m model -s

executor:  ## v2: run the tool executor on :8787
	uv run uvicorn executor.app:app --port 8787

sandboxed:  ## v2: run the six example tickets in sandboxed mode (needs make executor)
	uv run python -m lab.sandboxed
