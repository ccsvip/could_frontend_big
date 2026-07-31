#!/usr/bin/env bash
# One-time per-clone GitNexus bootstrap.
#
# Keeps the company and home machines aligned:
#   1. Enable the .githooks/ auto-index hooks (required once per clone).
#   2. Merge the omp MCP gitnexus entry (with pinned env) into ~/.omp/agent/mcp.json.
#   3. Let `gitnexus setup` configure Claude Code / Cursor / Codex MCP + skills.
#   4. Verify the installed gitnexus version matches the project expectation.
#
# Idempotent: safe to re-run. Never overwrites unrelated MCP servers.
set -Eeuo pipefail

EXPECTED_GITNEXUS_VERSION="1.6.9"
TEMPLATE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/templates" && pwd)/omp-mcp-gitnexus.json"
OMP_MCP_FILE="$HOME/.omp/agent/mcp.json"

info() { printf '\033[1;36m[gitnexus-bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[gitnexus-bootstrap]\033[0m warning: %s\n' "$*" >&2; }

# --- 1. hooks ----------------------------------------------------------------
if [[ "$(git config core.hooksPath 2>/dev/null)" != ".githooks" ]]; then
  git config core.hooksPath .githooks
  info "core.hooksPath -> .githooks (auto GitNexus indexing enabled)"
else
  info "core.hooksPath already set to .githooks"
fi

# --- 2. omp MCP merge --------------------------------------------------------
if [[ ! -f "$TEMPLATE_FILE" ]]; then
  warn "template missing: $TEMPLATE_FILE — skipping omp MCP config"
else
  mkdir -p "$(dirname "$OMP_MCP_FILE")"
  python3 - "$TEMPLATE_FILE" "$OMP_MCP_FILE" <<'PY'
import json
import sys

template_path, target_path = sys.argv[1], sys.argv[2]

with open(template_path, encoding="utf-8") as fh:
    template = json.load(fh)

try:
    with open(target_path, encoding="utf-8") as fh:
        target = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    target = {}

target.setdefault("mcpServers", {})
target["mcpServers"]["gitnexus"] = template["mcpServers"]["gitnexus"]

with open(target_path, "w", encoding="utf-8") as fh:
    json.dump(target, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  info "merged gitnexus MCP entry (env pinned) into $OMP_MCP_FILE"
  info "  restart omp for the running MCP server to pick up the new env"
fi

# --- 3. gitnexus setup (Claude Code + skills) --------------------------------
if command -v gitnexus >/dev/null 2>&1; then
  # `setup` writes only missing entries; existing config is preserved.
  gitnexus setup >/dev/null 2>&1 || warn "gitnexus setup reported issues (see output above)"
  info "gitnexus setup: MCP + skills configured for detected editors"
else
  warn "gitnexus not on PATH — run: npm install -g gitnexus, then re-run this script"
fi

# --- 4. version check ----------------------------------------------------------
if command -v gitnexus >/dev/null 2>&1; then
  installed="$(gitnexus --version 2>/dev/null | tail -n1 || true)"
  if [[ "$installed" == "$EXPECTED_GITNEXUS_VERSION" ]]; then
    info "gitnexus version $installed (matches expected)"
  else
    warn "gitnexus version $installed != expected $EXPECTED_GITNEXUS_VERSION — pin with: npm i -g gitnexus@$EXPECTED_GITNEXUS_VERSION"
  fi
fi

info "done. The .githooks hooks auto-index on commit/merge/checkout; index refresh: node .gitnexus/run.cjs analyze --index-only"
