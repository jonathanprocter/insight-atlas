#!/bin/bash
# InsightAtlas Portable Setup
# Run this on any machine to auto-configure everything.
# Works from: git clone, flash drive, or pCloud sync.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== InsightAtlas Setup ==="
echo ""

# ---------- DETECT OS ----------
OS="$(uname -s)"
case "$OS" in
    Darwin) PLATFORM="mac" ;;
    Linux)  PLATFORM="linux" ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
    *) PLATFORM="unknown" ;;
esac
echo "[1/6] Platform: $PLATFORM ($OS)"

# ---------- DETECT pCLOUD ----------
PCLOUD=""
for candidate in \
    "$HOME/pCloud Drive" \
    "$HOME/pCloudDrive" \
    "$HOME/pCloud Sync" \
    "$HOME/pCloudSync" \
    "/Volumes/pCloud" \
    ; do
    if [ -d "$candidate" ]; then
        PCLOUD="$candidate"
        break
    fi
done

# Check mounted volumes (flash drives, external)
if [ -z "$PCLOUD" ] && [ "$PLATFORM" = "mac" ]; then
    for vol in /Volumes/*/; do
        if [ -d "${vol}pCloud" ]; then
            PCLOUD="${vol}pCloud"
            break
        fi
        # Check if the volume itself IS a pCloud copy
        if [ -f "${vol}InsightAtlas/book_index.faiss" ]; then
            PCLOUD="$vol"
            break
        fi
    done
fi

if [ -n "$PCLOUD" ]; then
    echo "[2/6] pCloud found: $PCLOUD"
else
    echo "[2/6] pCloud not found (resource scanning will be limited)"
fi

# ---------- DETECT FAISS INDEX ----------
FAISS_IDX=""
FAISS_META=""
for loc in \
    "$PCLOUD/InsightAtlas" \
    "$HOME/Desktop" \
    "$SCRIPT_DIR" \
    "$PCLOUD" \
    ; do
    [ -z "$loc" ] && continue
    if [ -f "$loc/book_index.faiss" ] && [ -f "$loc/book_index_meta.json" ]; then
        FAISS_IDX="$loc/book_index.faiss"
        FAISS_META="$loc/book_index_meta.json"
        break
    fi
done

# Also check flash drives
if [ -z "$FAISS_IDX" ] && [ "$PLATFORM" = "mac" ]; then
    for vol in /Volumes/*/; do
        for sub in "" "InsightAtlas/" "InsightAtlas/data/"; do
            if [ -f "${vol}${sub}book_index.faiss" ]; then
                FAISS_IDX="${vol}${sub}book_index.faiss"
                FAISS_META="${vol}${sub}book_index_meta.json"
                break 2
            fi
        done
    done
fi

if [ -n "$FAISS_IDX" ]; then
    echo "[3/6] FAISS index: $FAISS_IDX"
else
    echo "[3/6] FAISS index not found (semantic search will be disabled)"
fi

# ---------- DETECT API KEYS ----------
ANTHROPIC_KEY=""
NOTION_KEY=""

# Source 1: existing .env in project
if [ -f "$SCRIPT_DIR/.env" ]; then
    existing_ant=$(grep "^ANTHROPIC_API_KEY=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d= -f2-)
    existing_not=$(grep "^NOTION_API_KEY=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d= -f2-)
    [ -n "$existing_ant" ] && [ "$existing_ant" != "your_key_here" ] && ANTHROPIC_KEY="$existing_ant"
    [ -n "$existing_not" ] && [ "$existing_not" != "your_key_here" ] && NOTION_KEY="$existing_not"
fi

# Source 2: shell environment / rc files
if [ -z "$ANTHROPIC_KEY" ]; then
    ANTHROPIC_KEY="${ANTHROPIC_API_KEY:-}"
fi
if [ -z "$ANTHROPIC_KEY" ]; then
    for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
        if [ -f "$rc" ]; then
            key=$(grep "^export ANTHROPIC_API_KEY=" "$rc" 2>/dev/null | head -1 | sed 's/^export ANTHROPIC_API_KEY=//;s/^"//;s/"$//')
            [ -n "$key" ] && ANTHROPIC_KEY="$key" && break
        fi
    done
fi

# Source 3: Claude MCP config (for Notion key)
if [ -z "$NOTION_KEY" ]; then
    if [ -f "$HOME/.claude/mcp.json" ]; then
        key=$(grep -o 'ntn_[A-Za-z0-9]*' "$HOME/.claude/mcp.json" 2>/dev/null | head -1)
        [ -n "$key" ] && NOTION_KEY="$key"
    fi
fi

# Source 4: flash drive secrets file
for vol in /Volumes/*/; do
    if [ -f "${vol}.insight-atlas-keys" ]; then
        echo "  Found keys on removable drive: ${vol}"
        source "${vol}.insight-atlas-keys"
        [ -n "$ANTHROPIC_API_KEY" ] && ANTHROPIC_KEY="$ANTHROPIC_API_KEY"
        [ -n "$NOTION_API_KEY" ] && NOTION_KEY="$NOTION_API_KEY"
        break
    fi
done

if [ -n "$ANTHROPIC_KEY" ]; then
    echo "[4/6] Anthropic key: found (${ANTHROPIC_KEY:0:12}...)"
else
    echo "[4/6] Anthropic key: NOT FOUND"
    read -p "  Enter ANTHROPIC_API_KEY (or press Enter to skip): " ANTHROPIC_KEY
fi

if [ -n "$NOTION_KEY" ]; then
    echo "[5/6] Notion key: found (${NOTION_KEY:0:8}...)"
else
    echo "[5/6] Notion key: NOT FOUND"
    read -p "  Enter NOTION_API_KEY (or press Enter to skip): " NOTION_KEY
fi

# ---------- WRITE .env ----------
cat > "$SCRIPT_DIR/.env" << ENVFILE
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
NOTION_API_KEY=${NOTION_KEY}
KMP_DUPLICATE_LIB_OK=TRUE
ENVFILE

# Add optional overrides if paths are non-default
if [ -n "$PCLOUD" ] && [ "$PCLOUD" != "$HOME/pCloud Drive" ]; then
    echo "PCLOUD_BASE=${PCLOUD}" >> "$SCRIPT_DIR/.env"
fi
if [ -n "$FAISS_IDX" ]; then
    echo "FAISS_INDEX_PATH=${FAISS_IDX}" >> "$SCRIPT_DIR/.env"
    echo "FAISS_META_PATH=${FAISS_META}" >> "$SCRIPT_DIR/.env"
fi

echo "[6/6] .env written"

# ---------- PYTHON VENV + DEPS ----------
echo ""
echo "=== Installing dependencies ==="

python3 -m venv "$SCRIPT_DIR/venv" 2>/dev/null || python -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"
pip install -q -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Setup complete ==="
echo ""
echo "  pCloud:    ${PCLOUD:-not found}"
echo "  FAISS:     ${FAISS_IDX:-not found}"
[ -n "$ANTHROPIC_KEY" ] && echo "  Anthropic: OK" || echo "  Anthropic: MISSING"
[ -n "$NOTION_KEY" ]    && echo "  Notion:    OK" || echo "  Notion:    MISSING"
echo ""
echo "Run:  ./run.sh"
