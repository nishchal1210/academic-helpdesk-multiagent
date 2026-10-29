#!/usr/bin/env bash
set -euo pipefail

# Override these two paths when running on another computer.
HELPDESK_OLLAMA_BIN="${HELPDESK_OLLAMA_BIN:-/home/divya/Nishchal_internship/ollama/bin/ollama}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/home/divya/Nishchal_internship/ollama_models}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-8192}"
export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_NO_CLOUD=true
exec "$HELPDESK_OLLAMA_BIN" serve
