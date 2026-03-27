#!/bin/bash
# claude-brain installer
# One-line install: curl -fsSL https://raw.githubusercontent.com/mikeadolan/claude-brain/main/install.sh | bash
#
# Checks prerequisites, clones the repo, installs dependencies, and launches brain-setup.py.

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "    ${GREEN}OK${NC}  $1"; }
fail() { echo -e "    ${RED}FAIL${NC}  $1"; }
warn() { echo -e "    ${YELLOW}WARN${NC}  $1"; }

echo ""
echo "  claude-brain installer"
echo "  ----------------------"
echo ""
echo "  Checking prerequisites..."
echo ""

ERRORS=0

# --- Python 3.10+ ---
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        ok "Python $PY_VERSION"
    else
        fail "Python $PY_VERSION (need 3.10+)"
        echo ""
        echo "  Install Python 3.10+:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "    brew install python@3.12"
        elif command -v dnf &>/dev/null; then
            echo "    sudo dnf install python3"
        elif command -v apt &>/dev/null; then
            echo "    sudo apt install python3"
        fi
        ERRORS=$((ERRORS + 1))
    fi
else
    fail "Python 3 not found"
    echo ""
    echo "  Install Python 3.10+:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    brew install python@3.12"
    elif command -v dnf &>/dev/null; then
        echo "    sudo dnf install python3"
    elif command -v apt &>/dev/null; then
        echo "    sudo apt install python3"
    fi
    ERRORS=$((ERRORS + 1))
fi

# --- pip3 ---
if command -v pip3 &>/dev/null; then
    ok "pip3"
elif python3 -m pip --version &>/dev/null 2>&1; then
    ok "pip3 (via python3 -m pip)"
else
    fail "pip3 not found"
    echo ""
    echo "  Install pip3:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    pip3 comes with Python from Homebrew"
    elif command -v dnf &>/dev/null; then
        echo "    sudo dnf install python3-pip"
    elif command -v apt &>/dev/null; then
        echo "    sudo apt install python3-pip"
    fi
    ERRORS=$((ERRORS + 1))
fi

# --- git ---
if command -v git &>/dev/null; then
    ok "git"
else
    fail "git not found"
    echo ""
    echo "  Install git:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    xcode-select --install"
    elif command -v dnf &>/dev/null; then
        echo "    sudo dnf install git"
    elif command -v apt &>/dev/null; then
        echo "    sudo apt install git"
    fi
    ERRORS=$((ERRORS + 1))
fi

# --- Claude Code ---
if command -v claude &>/dev/null; then
    CC_VERSION=$(claude --version 2>/dev/null | head -1 | grep -oP '[\d.]+' | head -1)
    if [ -n "$CC_VERSION" ]; then
        ok "Claude Code $CC_VERSION"
    else
        ok "Claude Code (version unknown)"
    fi
else
    fail "Claude Code not found"
    echo ""
    echo "  Install Claude Code:"
    echo "    npm install -g @anthropic-ai/claude-code"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# --- Abort if prerequisites missing ---
if [ $ERRORS -gt 0 ]; then
    echo -e "  ${RED}$ERRORS prerequisite(s) missing. Install them and run this script again.${NC}"
    echo ""
    exit 1
fi

echo -e "  ${GREEN}All prerequisites met.${NC}"
echo ""

# --- Ask install location ---
DEFAULT_DIR="$HOME/claude-brain"
read -p "  Install location [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

# Expand ~ if user typed it
INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"

# --- Check if already exists ---
if [ -d "$INSTALL_DIR" ]; then
    if [ -f "$INSTALL_DIR/config.yaml" ]; then
        echo ""
        echo "  claude-brain already exists at $INSTALL_DIR"
        read -p "  Update it? (git pull + pip install) [Y/n]: " UPDATE_CHOICE
        UPDATE_CHOICE="${UPDATE_CHOICE:-y}"
        if [[ "$UPDATE_CHOICE" =~ ^[Yy] ]]; then
            echo ""
            echo "  Updating..."
            cd "$INSTALL_DIR"
            git pull
            pip3 install -r requirements.txt
            echo ""
            echo -e "  ${GREEN}Updated successfully.${NC}"
            echo ""
            echo "  To re-run setup: python3 $INSTALL_DIR/scripts/brain-setup.py"
            echo ""
            exit 0
        else
            echo "  Skipped."
            exit 0
        fi
    else
        echo ""
        echo -e "  ${RED}Directory $INSTALL_DIR exists but is not a claude-brain install.${NC}"
        echo "  Choose a different location or remove the directory first."
        exit 1
    fi
fi

# --- Clone ---
echo ""
echo "  Cloning repository..."
git clone https://github.com/mikeadolan/claude-brain.git "$INSTALL_DIR"
echo -e "  ${GREEN}Cloned to $INSTALL_DIR${NC}"

# --- Install dependencies ---
echo ""
echo "  Installing dependencies..."
cd "$INSTALL_DIR"
pip3 install -r requirements.txt
echo ""
echo -e "  ${GREEN}Dependencies installed.${NC}"

# --- Launch setup ---
echo ""
echo "  Starting brain setup..."
echo "  (This will ask about your projects, database location, and more)"
echo ""
python3 scripts/brain-setup.py

echo ""
echo -e "  ${GREEN}claude-brain is installed and configured.${NC}"
echo ""
echo "  To start using it:"
echo "    cd $INSTALL_DIR/<your-project-folder>"
echo "    claude"
echo ""
echo "  The brain activates automatically. Type /brain-status to verify."
echo ""
