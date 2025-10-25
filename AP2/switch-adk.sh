#!/bin/bash
# Script to switch between local and official Google ADK versions

set -e

show_usage() {
    echo "Usage: $0 [local|official|status]"
    echo ""
    echo "Commands:"
    echo "  local    - Switch to local forked version (editable)"
    echo "  official - Switch to official PyPI version"
    echo "  status   - Check which version is currently active"
    echo ""
    echo "Examples:"
    echo "  ./switch-adk.sh local"
    echo "  ./switch-adk.sh official"
    echo "  ./switch-adk.sh status"
}

check_status() {
    echo "Checking current google-adk status..."
    echo ""
    if .venv/bin/python3 -c "import google.adk; print('✓ Installed:', google.adk.__file__); print('✓ Version:', google.adk.__version__)" 2>/dev/null; then
        echo ""
        if [[ $(uv pip list 2>/dev/null | grep "google-adk-local") ]]; then
            echo "Status: LOCAL VERSION (editable)"
        elif [[ $(uv pip list 2>/dev/null | grep "google-adk") ]]; then
            echo "Status: OFFICIAL VERSION (PyPI)"
        fi
    else
        echo "✗ google-adk is not installed"
        exit 1
    fi
}

if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

case "$1" in
    local)
        echo "Switching to local forked version of google-adk..."
        uv pip uninstall google-adk google-adk-local 2>/dev/null || true
        uv pip install -e google-adk-local/
        echo ""
        echo "✓ Successfully switched to local version!"
        echo "  Location: $(pwd)/google-adk-local/google/adk/"
        echo "  Any changes you make will be immediately available."
        echo ""
        echo "⚠️  Note: Running 'uv sync' may try to reinstall. If that happens,"
        echo "   just run './switch-adk.sh local' again after sync."
        ;;
    official)
        echo "Switching to official google-adk from PyPI..."
        
        # Update samples/python/pyproject.toml
        sed -i.bak 's/"google-adk-local"/"google-adk"/' samples/python/pyproject.toml
        sed -i.bak '/google-adk-local = { workspace = true }/d' samples/python/pyproject.toml
        rm samples/python/pyproject.toml.bak 2>/dev/null || true
        
        # Update root pyproject.toml
        sed -i.bak 's/members = \["samples\/python", "google-adk-local"\]/members = ["samples\/python"]/' pyproject.toml
        rm pyproject.toml.bak 2>/dev/null || true
        
        uv pip uninstall google-adk google-adk-local 2>/dev/null || true
        uv pip install google-adk
        echo ""
        echo "✓ Successfully switched to official version!"
        ;;
    status)
        check_status
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        show_usage
        exit 1
        ;;
esac

