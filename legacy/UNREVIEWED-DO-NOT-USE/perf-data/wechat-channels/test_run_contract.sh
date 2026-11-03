#!/usr/bin/env bash
# Contract check for wechat-channels/run.sh.
# This script invokes the adapter wrapper. It was not executed as part of the
# security change. Expected contract after the fix:
# - CHEAT_PYTHON outside the project .venv is not executed
# - a pre-existing report.md survives dependency and login failures
set -euo pipefail

ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
TMP_ROOT="$(mktemp -d)"
trap 'case "$TMP_ROOT" in /tmp/*|/var/tmp/*) rm -rf -- "$TMP_ROOT" ;; esac' EXIT

PROJECT="$TMP_ROOT/project"
VIDEO_FOLDER="$PROJECT/videos/example"
FAKE_PYTHON="$TMP_ROOT/fake-python"
FAKE_RAN="$TMP_ROOT/fake-ran"

mkdir -p "$VIDEO_FOLDER"
printf '{}\n' > "$PROJECT/.cheat-state.json"
printf 'stale report\n' > "$VIDEO_FOLDER/report.md"

cat > "$FAKE_PYTHON" <<FAKE
#!/usr/bin/env bash
echo executed > "$FAKE_RAN"
exit 7
FAKE
chmod +x "$FAKE_PYTHON"

set +e
CHEAT_PYTHON="$FAKE_PYTHON" bash "$ADAPTER_DIR/run.sh" example "$VIDEO_FOLDER" >/dev/null 2>&1
status=$?
set -e

if [[ "$status" -eq 7 || -f "$FAKE_RAN" ]]; then
  echo "CHEAT_PYTHON outside .venv was executed" >&2
  exit 1
fi
if [[ ! -f "$VIDEO_FOLDER/report.md" ]]; then
  echo "pre-existing report.md was deleted" >&2
  exit 1
fi
if [[ "$status" -eq 0 ]]; then
  echo "run succeeded without a confirmed venv interpreter" >&2
  exit 1
fi

echo "run.sh failure contract: ok"
