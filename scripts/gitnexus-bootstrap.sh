#!/usr/bin/env bash
# One-time per-clone GitNexus bootstrap.
#
# Keeps the company and home machines aligned:
#   1. Enable the .githooks/ auto-index hooks (required once per clone).
#   2. Merge the omp MCP gitnexus entry (with pinned env) into ~/.omp/agent/mcp.json.
#   3. Let `gitnexus setup` configure Claude Code MCP + skills (codex is merged in step 4
#      AFTER setup because `setup -c codex` rewrites the gitnexus section).
#   4. Merge the env-pinned gitnexus MCP entry into ~/.codex/config.toml (Codex).
#   5. Verify the installed gitnexus version matches the project expectation.
#
# Idempotent: safe to re-run. Never overwrites unrelated MCP servers.
set -Eeuo pipefail

EXPECTED_GITNEXUS_VERSION="1.6.9"
GITNEXUS_ENV_VARS=(
  "GITNEXUS_FTS_CJK_SEGMENTATION=bigram"
  "GITNEXUS_WAL_CHECKPOINT_THRESHOLD=67108864"
)
TEMPLATE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/templates" && pwd)/omp-mcp-gitnexus.json"
OMP_MCP_FILE="$HOME/.omp/agent/mcp.json"
CODEX_CONFIG_FILE="$HOME/.codex/config.toml"

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
  # Scope to claude-code so it never rewrites the codex gitnexus section
  # (which we merge with env in step 4).
  gitnexus setup -c claude >/dev/null 2>&1 || warn "gitnexus setup reported issues (see output above)"
  info "gitnexus setup: MCP + skills configured for Claude Code"
else
  warn "gitnexus not on PATH — run: npm install -g gitnexus, then re-run this script"
fi

# --- 4. Codex MCP merge (~/.codex/config.toml) --------------------------------
if [[ -f "$CODEX_CONFIG_FILE" ]]; then
  python3 - "$CODEX_CONFIG_FILE" "${GITNEXUS_ENV_VARS[@]}" <<'PY'
import sys
import re

path = sys.argv[1]
env_vars = sys.argv[2:]

with open(path, encoding="utf-8") as fh:
    content = fh.read()

env_line = "env = { " + ", ".join(f'{k} = \"{v}\"' for k, v in (e.split("=", 1) for e in env_vars)) + " }"
section = "[mcp_servers.gitnexus]"

if section in content:
    # Replace any existing env= line inside the section; otherwise append it
    # right after the section header line.
    lines = content.splitlines()
    out = []
    in_section = False
    env_replaced = False
    header_index = None
    for i, line in enumerate(lines):
        if line.strip() == section:
            in_section = True
            header_index = i
            out.append(line)
            continue
        if in_section:
            stripped = line.strip()
            # env= must be matched before the top-level exit check: the line
            # may or may not be indented, and matching it first keeps the
            # replace idempotent across re-runs.
            if stripped.startswith("env ="):
                out.append(env_line)
                env_replaced = True
                continue
            # A new top-level key ends the section block.
            if stripped and not line.startswith((" ", "\t", "#", ";")):
                in_section = False
        out.append(line)
    if not env_replaced and header_index is not None:
        # Insert env as the first key of the section.
        out.insert(header_index + 1, env_line)
    content = "\n".join(out) + "\n"
else:
    content = content.rstrip() + "\n\n" + section + "\ncommand = \"gitnexus\"\nargs = [\"mcp\"]\n" + env_line + "\n"

with open(path, "w", encoding="utf-8") as fh:
    fh.write(content)
PY
  info "merged env-pinned gitnexus MCP entry into $CODEX_CONFIG_FILE"
else
  warn "$CODEX_CONFIG_FILE not found — skip Codex MCP config (install codex or run gitnexus setup -c codex)"
fi

# --- 5. version check ----------------------------------------------------------
if command -v gitnexus >/dev/null 2>&1; then
  installed="$(gitnexus --version 2>/dev/null | tail -n1 || true)"
  if [[ "$installed" == "$EXPECTED_GITNEXUS_VERSION" ]]; then
    info "gitnexus version $installed (matches expected)"
  else
    warn "gitnexus version $installed != expected $EXPECTED_GITNEXUS_VERSION — pin with: npm i -g gitnexus@$EXPECTED_GITNEXUS_VERSION"
  fi
fi

info "done. The .githooks hooks auto-index on commit/merge/checkout; index refresh: node .gitnexus/run.cjs analyze --index-only"
