#!/usr/bin/env bash
#
# cheat-on-content / prediction-immutability hook
#
# Fail closed. This script does not grant a bypass, including when
# CHEAT_BYPASS_IMMUTABILITY is set. Empty input, unparseable input, a missing
# interpreter, and any edit that cannot be proven to stay outside every
# prediction section are rejected.
#
# Host behavior is NOT verified in this repository:
# - Whether the configured matcher actually runs this script for every tool
#   name depends on the host and has not been tested here.
# - Whether exit code 1 actually cancels the tool call has not been tested here.
# A deny from this script is not a proof that the prediction file is immutable.

set -uo pipefail

if [[ -n "${CHEAT_BYPASS_IMMUTABILITY+x}" ]]; then
  echo "[cheat-on-content] CHEAT_BYPASS_IMMUTABILITY is ignored and does not permit edits." >&2
fi

input=$(cat || true)
if [[ -z "$input" ]]; then
  echo "BLOCKED: empty hook input; refusing because the target cannot be judged." >&2
  echo "Host enforcement of this exit code has not been verified." >&2
  exit 1
fi

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GUARD="$SCRIPT_DIR/prediction_guard.py"

if [[ ! -f "$GUARD" ]]; then
  echo "BLOCKED: $GUARD is missing; refusing because the edit cannot be checked." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "BLOCKED: python3 is missing; refusing because the edit cannot be checked." >&2
  exit 1
fi

printf '%s' "$input" | python3 "$GUARD"
status=$?
exit "$status"
