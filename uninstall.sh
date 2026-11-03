#!/usr/bin/env bash
#
# cheat-on-content / uninstall.sh
#
# Removes the 15 cheat-on-content skills from Claude Code and/or Codex skill dirs.
#
# Does NOT touch any content project's data (.cheat-state.json, predictions/,
# rubric_notes.md, candidates.md, etc.) — those live in your content directories
# and uninstalling the skill leaves your work intact.
#
# Only removes a skill the installer can confirm it created: a symlink whose
# target is this checkout, or a directory containing .cheat-on-content-managed.
# Same-named directories without that marker are left in place.
#
# Usage:
#   bash uninstall.sh          # remove Claude Code install (default)
#   bash uninstall.sh --codex  # remove Codex install
#   bash uninstall.sh --all    # remove both
#
# To re-install: bash install.sh

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# shellcheck source=tools/managed_install.sh
source "$SCRIPT_DIR/tools/managed_install.sh"

skill_source() {
  local skill="$1"
  if [[ "$skill" == "cheat-on-content" ]]; then
    echo "$SCRIPT_DIR"
  else
    echo "$SCRIPT_DIR/skills/$skill"
  fi
}

SUB_SKILLS=(
  cheat-init
  cheat-learn-from
  cheat-seed
  cheat-score
  cheat-score-blind
  cheat-predict
  cheat-shoot
  cheat-publish
  cheat-retro
  cheat-persona
  cheat-bump
  cheat-recommend
  cheat-trends
  cheat-status
  cheat-migrate
)

CLAUDE_SKILLS=("${SUB_SKILLS[@]}")
CODEX_SKILLS=(cheat-on-content "${SUB_SKILLS[@]}")

TARGET_AGENT="claude"
for arg in "$@"; do
  case "$arg" in
    --claude)
      TARGET_AGENT="claude"
      ;;
    --codex)
      TARGET_AGENT="codex"
      ;;
    --all)
      TARGET_AGENT="all"
      ;;
    --help|-h)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $arg"
      echo "   Usage: bash uninstall.sh [--claude|--codex|--all]"
      exit 1
      ;;
  esac
done

REMOVED=0

remove_skills() {
  local label="$1"
  local target_dir="$2"
  shift 2

  echo ""
  echo "Removing cheat-on-content from $label:"
  echo "  target: $target_dir/"
  echo ""

  for s in "$@"; do
    local target="$target_dir/$s"
    local src_real
    src_real="$(realpath -- "$(skill_source "$s")")"
    if [[ ! -e "$target" && ! -L "$target" ]]; then
      echo "  · not found:         $s (skipped)"
      continue
    fi
    if cheat_remove_confirmed_dest "$target" "$s" "$src_real" "$target_dir"; then
      echo "  ✓ removed confirmed install: $s"
      REMOVED=$((REMOVED + 1))
    else
      echo "  · skipped (not a confirmed cheat-on-content install, left in place): $s"
    fi
  done
}

if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Claude Code" "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}"
fi

if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Codex" "$HOME/.codex/skills" "${CODEX_SKILLS[@]}"
fi

echo ""
if [[ $REMOVED -gt 0 ]]; then
  echo "✅ Uninstalled $REMOVED skill(s)."
else
  echo "ℹ️  Nothing to uninstall."
fi
echo ""
echo "Note: your content projects' data (predictions/, rubric_notes.md, .cheat-state.json,"
echo "      .cheat-hooks/, candidates.md, etc.) are NOT touched. They live in each content"
echo "      project directory. To clean a specific content project, delete those files manually."
echo ""
echo "To re-install: bash install.sh [--codex|--all] (from cheat-on-content source root)"
echo ""
