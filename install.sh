#!/usr/bin/env bash
#
# cheat-on-content / install.sh
#
# Symlinks the 15 sub-skills into Claude Code and/or Codex skill directories so
# agents can find them globally. Re-runnable. An existing path is replaced only
# when it is a symlink to this checkout or a directory marked by this installer.
# Other same-named directories are left in place.
#
# After install, in any content project directory: open Claude Code → say "初始化"
# → /cheat-init runs the onboarding.
#
# To uninstall: bash uninstall.sh
#
# Usage:
#   bash install.sh                    # Claude Code install, symlink mode (default)
#   bash install.sh --copy             # Claude Code install, copy mode
#   bash install.sh --codex            # Codex install into ~/.codex/skills/
#   bash install.sh --all              # install for Claude Code and Codex
#   bash install.sh --codex --copy     # Codex install, copy mode
#   bash install.sh --reinstall-hooks <project-dir>
#                                      # rewrite hook scripts in an existing user project's .cheat-hooks/
#                                      # (use after git pull when CHANGELOG mentions hook script changes;
#                                      #  does NOT touch .cheat-state.json or any user data)

set -euo pipefail

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

# Resolve the directory containing THIS script (the source root) — needed early for both modes
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# shellcheck source=tools/managed_install.sh
source "$SCRIPT_DIR/tools/managed_install.sh"

MODE="symlink"
TARGET_AGENT="claude"

# --- --reinstall-hooks branch: rewrite a user project's hook scripts only ---
if [[ "${1:-}" == "--reinstall-hooks" ]]; then
  PROJECT_DIR="${2:-}"
  if [[ -z "$PROJECT_DIR" ]]; then
    echo "❌ Usage: bash install.sh --reinstall-hooks <path-to-user-project>"
    echo "   The user project must already have been initialized via /cheat-init."
    exit 1
  fi
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "❌ Project dir not found: $PROJECT_DIR"
    exit 1
  fi
  if [[ ! -f "$PROJECT_DIR/.cheat-state.json" ]]; then
    echo "❌ $PROJECT_DIR is not a cheat-on-content project (no .cheat-state.json)."
    echo "   Run /cheat-init in that directory first."
    exit 1
  fi

  HOOK_DST="$PROJECT_DIR/.cheat-hooks"
  mkdir -p "$HOOK_DST"

  echo ""
  echo "Reinstalling hook scripts in: $PROJECT_DIR"
  echo "  source: $SCRIPT_DIR/hooks/"
  echo ""

  for hook_script in prediction-immutability.sh prediction_guard.py session-start.sh log-event.sh; do
    if [[ -f "$SCRIPT_DIR/hooks/$hook_script" ]]; then
      cp "$SCRIPT_DIR/hooks/$hook_script" "$HOOK_DST/$hook_script"
      if [[ "$hook_script" == *.sh ]]; then
        chmod +x "$HOOK_DST/$hook_script"
      fi
      echo "  ✓ updated: .cheat-hooks/$hook_script"
    else
      echo "  ⚠️  missing in source: hooks/$hook_script (skipped)"
    fi
  done

  echo ""
  echo "✅ Hook scripts reinstalled."
  echo ""
  echo "Note: This did NOT touch:"
  echo "  - .cheat-state.json (your data)"
  echo "  - .claude/settings.json (hook registration — should still point at .cheat-hooks/)"
  echo "  - rubric_notes.md / predictions/ / videos/ (your work)"
  echo ""
  echo "If schema also changed (CHANGELOG marks BREAKING), additionally run /cheat-migrate"
  echo "in Claude Code from your project directory."
  echo ""
  exit 0
fi

for arg in "$@"; do
  case "$arg" in
    --copy)
      MODE="copy"
      ;;
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
      sed -n '1,35p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $arg"
      echo "   Usage: bash install.sh [--copy] [--claude|--codex|--all]"
      exit 1
      ;;
  esac
done

# Sanity check: confirm we're in the cheat-on-content root
if [[ ! -f "$SCRIPT_DIR/SKILL.md" ]]; then
  echo "❌ Missing: $SCRIPT_DIR/SKILL.md"
  echo "   Are you running install.sh from the cheat-on-content root?"
  exit 1
fi

for s in "${SUB_SKILLS[@]}"; do
  if [[ ! -f "$SCRIPT_DIR/skills/$s/SKILL.md" ]]; then
    echo "❌ Missing: $SCRIPT_DIR/skills/$s/SKILL.md"
    echo "   Are you running install.sh from the cheat-on-content root?"
    exit 1
  fi
done

skill_source() {
  local skill="$1"
  if [[ "$skill" == "cheat-on-content" ]]; then
    echo "$SCRIPT_DIR"
  else
    echo "$SCRIPT_DIR/skills/$skill"
  fi
}

detect_conflicts() {
  local target_dir="$1"
  shift
  local warned=0

  for s in "$@"; do
    local src
    src=$(skill_source "$s")
    local target="$target_dir/$s"
    if [[ -e "$target" || -L "$target" ]]; then
      if [[ -L "$target" ]]; then
        local existing
        existing=$(readlink "$target")
        if [[ "$existing" != "$src" ]]; then
          echo "⚠️  $target already symlinked to: $existing"
          warned=1
        fi
      else
        echo "⚠️  $target exists (not a symlink) — will be overwritten"
        warned=1
      fi
    fi
  done

  return "$warned"
}

install_skills() {
  local label="$1"
  local target_dir="$2"
  shift 2

  mkdir -p "$target_dir"

  echo ""
  echo "Installing cheat-on-content for $label (mode: $MODE)"
  echo "  source: $SCRIPT_DIR"
  echo "  target: $target_dir/"
  echo ""

  local failed=0
  for s in "$@"; do
    local src src_real dst
    src=$(skill_source "$s")
    src_real="$(realpath -- "$src")"
    dst="$target_dir/$s"

    if [[ -e "$dst" || -L "$dst" ]]; then
      if ! cheat_remove_confirmed_dest "$dst" "$s" "$src_real" "$target_dir"; then
        echo "  ❌ 不删除未经确认的路径: $dst"
        echo "     只有指向本仓库的符号链接，或带 .cheat-on-content-managed 标记的目录，才会被替换。"
        failed=1
        continue
      fi
    fi

    if [[ "$MODE" == "symlink" ]]; then
      ln -s "$src" "$dst"
      echo "  ✓ symlinked: $s"
    else
      cp -R "$src" "$dst"
      if [[ "$s" == "cheat-on-content" ]]; then
        cheat_strip_copied_git "$dst"
      fi
      cheat_write_marker "$dst" "$s" "$src_real"
      echo "  ✓ copied:    $s"
    fi
  done
  return "$failed"
}

FAILED=0
if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  detect_conflicts "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}" || true
  install_skills "Claude Code" "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}" || FAILED=1
fi

if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  detect_conflicts "$HOME/.codex/skills" "${CODEX_SKILLS[@]}" || true
  install_skills "Codex" "$HOME/.codex/skills" "${CODEX_SKILLS[@]}" || FAILED=1
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo ""
  echo "❌ 有未经确认的同名路径未删除。把那些目录移走后可以重试。"
  exit 1
fi

echo ""
echo "✅ Install complete!"
echo ""
echo "Next steps:"
echo "  1. cd into your content project (or create one):"
echo "       mkdir ~/my-channel && cd ~/my-channel"
echo ""
echo "  2. Open Claude Code or Codex in that directory"
echo ""
echo "  3. In the chat, say:"
echo "       初始化"
echo "       (or: 初始化 cheat-on-content)"
echo ""
if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  echo "Verify Claude install: ls -la ~/.claude/skills/ | grep cheat"
fi
if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  echo "Verify Codex install:  ls -la ~/.codex/skills/ | grep cheat"
  echo "Note: restart Codex if the new skills do not appear in the current session."
fi
echo ""
if [[ "$MODE" == "symlink" ]]; then
  echo "ℹ️  Mode: symlink — edits to source SKILL.md files take effect immediately."
  if [[ "$TARGET_AGENT" == "codex" ]]; then
    echo "   To switch to frozen copy: bash install.sh --codex --copy"
  elif [[ "$TARGET_AGENT" == "all" ]]; then
    echo "   To switch to frozen copy: bash install.sh --all --copy"
  else
    echo "   To switch to frozen copy: bash install.sh --copy"
  fi
else
  echo "ℹ️  Mode: copy — frozen at install time. Re-run install.sh to update."
fi
echo ""
