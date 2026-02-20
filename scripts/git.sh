#!/usr/bin/env bash
# Git workflow scripts for castmasta
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STRUCTURE_FILE="$REPO_ROOT/directory_structure.md"

# ---------------------------------------------------------------------------
# Update directory_structure.md
# Call this whenever files are created or deleted.
# ---------------------------------------------------------------------------
update_structure() {
    echo "# Directory Structure" > "$STRUCTURE_FILE"
    echo "" >> "$STRUCTURE_FILE"
    echo '```' >> "$STRUCTURE_FILE"
    find "$REPO_ROOT" \
        -not -path '*/.git/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/.venv/*' \
        -not -path '*.egg-info/*' \
        -not -path '*/.pytest_cache/*' \
        -not -path '*/.ruff_cache/*' \
        -not -path '*/.aider*' \
        | sort | sed "s|$REPO_ROOT/||g" >> "$STRUCTURE_FILE"
    echo '```' >> "$STRUCTURE_FILE"
    echo "Updated $STRUCTURE_FILE"
}

# ---------------------------------------------------------------------------
# Commit all staged + unstaged changes with a message
# Usage: ./scripts/git.sh commit "feat: your message"
# ---------------------------------------------------------------------------
commit() {
    local msg="${1:?Usage: $0 commit <message>}"
    update_structure
    git -C "$REPO_ROOT" add directory_structure.md
    git -C "$REPO_ROOT" add -A
    git -C "$REPO_ROOT" commit -m "$msg

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
}

# ---------------------------------------------------------------------------
# Push to origin main
# ---------------------------------------------------------------------------
push() {
    git -C "$REPO_ROOT" push origin main
}

# ---------------------------------------------------------------------------
# Run full test suite
# ---------------------------------------------------------------------------
test() {
    "$REPO_ROOT/.venv/bin/pytest" "$REPO_ROOT/tests/" -v
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
CMD="${1:-help}"
shift || true

case "$CMD" in
    update-structure) update_structure ;;
    commit)           commit "$@" ;;
    push)             push ;;
    test)             test ;;
    help|*)
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  update-structure   Regenerate directory_structure.md"
        echo "  commit <message>   Stage all changes, update structure, commit"
        echo "  push               Push to origin main"
        echo "  test               Run full test suite"
        ;;
esac
