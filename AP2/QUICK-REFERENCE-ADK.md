# Quick Reference: Google ADK Local Fork

## ✅ Current Setup
- **Local fork location**: `google-adk-local/google/adk/`
- **Active version**: LOCAL (editable)
- **Package name**: `google-adk-local` (version 1.13.0+local)
- **Python imports**: Use `import google.adk` (unchanged!)
- **CLI command**: `.venv/bin/adk` or just `adk` if venv is activated

## 🔧 Common Commands

### Check Status
```bash
./switch-adk.sh status
```

### Switch to Local Version
```bash
./switch-adk.sh local
```

### Switch to Official Version
```bash
./switch-adk.sh official
```

## 📝 Making Changes

1. Edit files in `google-adk-local/google/adk/`
2. Changes are **immediately available** (no reinstall needed)
3. Test your changes
4. Done!

## ⚠️ Important Notes

### After `uv sync`
If you run `uv sync` and the local version gets uninstalled, just run:
```bash
./switch-adk.sh local
```

### Project Dependencies
The following files have been updated to use the local fork:
- ✅ `samples/python/pyproject.toml` - uses `google-adk-local`
- ✅ Root `pyproject.toml` - includes local fork in workspace

## 🗂️ Key Directories in Local Fork

```
google-adk-local/google/adk/
├── cli/              # CLI tools and web interface
├── agents/           # Agent implementations
├── a2a/             # Agent-to-Agent protocol
├── tools/           # Built-in tools
├── auth/            # Authentication
├── models/          # Model integrations
└── ...
```

## 🧪 Quick Tests

### Test Python imports
```bash
.venv/bin/python3 -c "import google.adk; print(google.adk.__file__)"
```
**Expected output**: Should show path to `google-adk-local/google/adk/__init__.py`

### Test CLI command
```bash
.venv/bin/adk --version
```
**Expected output**: `adk, version 1.13.0`

## 📚 Full Documentation

See `GOOGLE-ADK-LOCAL.md` for complete documentation.

