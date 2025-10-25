# Local Fork of Google ADK

This is a local fork of the Google Agent Development Kit (ADK) package for development purposes.

## Original Source
- Package: `google-adk` version 1.13.0
- Repository: https://github.com/google/adk-python
- Documentation: https://google.github.io/adk-docs/

## Installation

To install this local version in editable mode:

```bash
pip uninstall google-adk  # Remove the original package first
pip install -e google-adk-local/
```

This will install the package in editable mode, so any changes you make to the code will be immediately reflected without needing to reinstall.

## Reverting to Official Version

To switch back to the official version:

```bash
pip uninstall google-adk-local
pip install google-adk
```

## Development

The package source is located in `google-adk-local/google/adk/`.

Make your modifications directly in this directory, and they will be available immediately when you import `google.adk` in your code.

## License

This is a fork of the Apache 2.0 licensed Google ADK project. See LICENSE file for details.

