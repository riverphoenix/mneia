#!/usr/bin/env bash
# Install the mneia Claude Code skill and optionally generate initial context.
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)/skills/claude-code/mneia"
SKILL_DST="${HOME}/.agents/skills/mneia"
AGENTS_DIR="${HOME}/.agents/skills"

# ── helpers ──────────────────────────────────────────────────────────────────
green()  { printf "\033[0;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[0;33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

# ── 1. verify source ──────────────────────────────────────────────────────────
if [[ ! -f "${SKILL_SRC}/SKILL.md" ]]; then
    echo "ERROR: skill source not found at ${SKILL_SRC}" >&2
    exit 1
fi

bold "Installing mneia Claude Code skill..."
echo ""

# ── 2. create agents/skills directory ────────────────────────────────────────
mkdir -p "${AGENTS_DIR}"

# ── 3. copy skill ─────────────────────────────────────────────────────────────
if [[ -d "${SKILL_DST}" ]]; then
    yellow "Updating existing skill at ${SKILL_DST}"
    rm -rf "${SKILL_DST}"
fi
cp -r "${SKILL_SRC}" "${SKILL_DST}"
green "✓ Skill installed → ${SKILL_DST}"

# ── 4. generate Claude context file ──────────────────────────────────────────
if command -v mneia &>/dev/null; then
    echo ""
    yellow "Generating Claude Code context from your knowledge base..."
    if mneia context generate-claude 2>/dev/null; then
        green "✓ Context written → ~/.mneia/claude-context.md"
    else
        yellow "⚠  Context generation skipped (run 'mneia sync' first to ingest data)"
    fi
else
    echo ""
    yellow "⚠  mneia not found in PATH — install it first: pip install mneia"
fi

# ── 5. check CLAUDE.md pointer ───────────────────────────────────────────────
GLOBAL_CLAUDE="${HOME}/.claude/CLAUDE.md"
CONTEXT_FILE="${HOME}/.mneia/claude-context.md"
POINTER="@${CONTEXT_FILE}"

if [[ -f "${GLOBAL_CLAUDE}" ]]; then
    if grep -qF "${CONTEXT_FILE}" "${GLOBAL_CLAUDE}" 2>/dev/null; then
        green "✓ CLAUDE.md already references mneia context"
    else
        echo ""
        read -r -p "Add mneia context reference to ~/.claude/CLAUDE.md? [Y/n] " answer
        answer="${answer:-Y}"
        if [[ "${answer}" =~ ^[Yy]$ ]]; then
            printf "\n\n# mneia personal context\n%s\n" "${POINTER}" >> "${GLOBAL_CLAUDE}"
            green "✓ Added to ~/.claude/CLAUDE.md"
        fi
    fi
else
    echo ""
    yellow "No ~/.claude/CLAUDE.md found — creating one with mneia context pointer"
    printf "# mneia personal context\n%s\n" "${POINTER}" > "${GLOBAL_CLAUDE}"
    green "✓ Created ~/.claude/CLAUDE.md"
fi

# ── 6. done ───────────────────────────────────────────────────────────────────
echo ""
bold "Done! The mneia skill is ready in Claude Code."
echo ""
echo "  Try: 'ask mneia what I worked on last week'"
echo "  Or:  'run mneia status'"
echo "  Or:  'set up mneia for me'"
echo ""
echo "  Refresh context after each sync:"
echo "    mneia context generate-claude"
echo ""
