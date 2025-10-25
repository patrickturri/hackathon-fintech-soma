# Google ADK Local Fork Setup

## Summary

You now have a local, editable fork of the Google Agent Development Kit (ADK) installed! 🎉

## What Was Done

1. **Created local fork**: Copied `google-adk` version 1.13.0 from site-packages to `google-adk-local/`
2. **Made it installable**: Added `pyproject.toml`, `README.md`, and proper package structure
3. **Installed in editable mode**: Any changes you make to the code are immediately available
4. **Created helper script**: `switch-adk.sh` to easily switch between local and official versions

## Current Status

✓ **Local version is active**: `google-adk-local 1.13.0+local`  
✓ **Location**: `/Users/john/Documents/hackatons/soma20251025/hackathon-fintech-soma/AP2/google-adk-local/google/adk/`

## Making Changes

Simply edit files in `google-adk-local/google/adk/` - changes are live immediately!

**Example locations:**
- CLI tools: `google-adk-local/google/adk/cli/`
- Agents: `google-adk-local/google/adk/agents/`
- A2A integration: `google-adk-local/google/adk/a2a/`
- Tools: `google-adk-local/google/adk/tools/`

## Switching Versions

### Switch to local version
```bash
./switch-adk.sh local
```

### Switch back to official version
```bash
./switch-adk.sh official
```

### Check which version is active
```bash
./switch-adk.sh status
```

## Important Note About `uv sync`

⚠️ **When you run `uv sync`, it may try to reconcile dependencies and could uninstall the local version.**

If this happens, simply run:
```bash
./switch-adk.sh local
```

This will reinstall the local editable version.

## Verify Which Version Is Active

```bash
uv pip list | grep google-adk
```

Or in Python:
```python
import google.adk
print(google.adk.__file__)
print(google.adk.__version__)
```

## Tips

1. **Keep track of your changes**: Consider creating a git branch in `google-adk-local/` if you want version control
2. **Test thoroughly**: Since you're modifying a core library, test your changes well
3. **Upstream improvements**: If you make useful changes, consider contributing them back to https://github.com/google/adk-python

## Reverting Changes

If you want to start fresh:
```bash
./switch-adk.sh official  # Switch to official version
rm -rf google-adk-local/  # Remove the local fork
# Then re-run the fork setup if needed
```

## Need Help?

- Official docs: https://google.github.io/adk-docs/
- GitHub repo: https://github.com/google/adk-python
- Local README: `google-adk-local/README.md`

