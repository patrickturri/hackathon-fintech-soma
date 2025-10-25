#!/bin/bash
# Script to switch between local and official Google ADK versions

set -e

show_usage() {
    echo "Usage: $0 [local|official]"
    echo ""
    echo "Commands:"
    echo "  local    - Switch to local forked version (editable)"
    echo "  official - Switch to official PyPI version"
    echo ""
    echo "Examples:"
    echo "  ./switch-adk.sh local"
    echo "  ./switch-adk.sh official"
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
        ;;
    official)
        echo "Switching to official google-adk from PyPI..."
        uv pip uninstall google-adk google-adk-local 2>/dev/null || true
        uv pip install google-adk
        echo ""
        echo "✓ Successfully switched to official version!"
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        show_usage
        exit 1
        ;;
esac

