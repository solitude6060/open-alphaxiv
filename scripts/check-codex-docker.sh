#!/usr/bin/env bash
set -euo pipefail

codex_bin="${OPEN_ALPHAXIV_HOST_CODEX_BIN:-}"
if [[ -z "$codex_bin" ]]; then
  codex_bin="$(command -v codex || true)"
fi

if [[ -z "$codex_bin" ]]; then
  echo "Codex CLI was not found on PATH."
  echo "Install or expose Codex on the host first, then rerun this script."
  exit 1
fi

codex_bin_dir="$(cd "$(dirname "$codex_bin")" && pwd)"
node_prefix="$(cd "$codex_bin_dir/.." && pwd)"
codex_home="${OPEN_ALPHAXIV_HOST_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}"

echo "Detected Codex CLI: $codex_bin"
echo "Detected host Node prefix: $node_prefix"
echo "Detected host Codex home: $codex_home"

if [[ ! -e "$codex_bin_dir/codex" ]]; then
  echo "Expected $codex_bin_dir/codex to exist."
  exit 1
fi

exec_help="$("$codex_bin_dir/codex" exec --help 2>&1 || true)"
for required_flag in --ephemeral --sandbox --skip-git-repo-check; do
  if ! grep -q -- "$required_flag" <<<"$exec_help"; then
    echo "Codex CLI does not report required flag for paper chat: $required_flag"
    echo "Upgrade Codex CLI or set OPEN_ALPHAXIV_HOST_CODEX_BIN to a compatible install."
    exit 1
  fi
done

if [[ ! -d "$codex_home" ]]; then
  echo "Codex home directory does not exist: $codex_home"
  echo "Run codex login on the host first, or set OPEN_ALPHAXIV_HOST_CODEX_HOME."
  exit 1
fi

if [[ ! -f "$codex_home/auth.json" && -z "${CODEX_ACCESS_TOKEN:-}" && -z "${CODEX_API_KEY:-}" ]]; then
  echo "No auth.json, CODEX_ACCESS_TOKEN, or CODEX_API_KEY was detected."
  echo "Run codex login on the host first, or provide a token/key to the API runtime."
  exit 1
fi

cat <<EOF

Use these commands to start Open AlphaXiv with the local Codex agent mounted:

export OPEN_ALPHAXIV_HOST_NODE_PREFIX="$node_prefix"
export OPEN_ALPHAXIV_HOST_CODEX_HOME="$codex_home"
docker compose -f docker-compose.yml -f docker-compose.codex.yml up -d --build api web worker

After startup, verify:

curl -s http://127.0.0.1:8000/api/codex/status
EOF
