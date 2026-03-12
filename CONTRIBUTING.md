# Contributing to vs-cli

First off, thank you for considering contributing to `vs-cli`! 

## Our Philosophy
`vs-cli` is designed to be a "drop-in" editor for terminal environments. To maintain this, we have a few **non-negotiable** rules:

1. **Single File:** The entire editor must remain in `vs_cli.py`.
2. **Line Limit:** We aim to keep the code under **~1200 lines**. Efficiency is key.
3. **No New Dependencies:** `blessed` is our only third-party dependency. Do not add others.
4. **No Config Files:** Configuration should be done by editing the source or via environment variables.

## How to Contribute
- **Bug Reports:** Open an issue with your OS, terminal emulator, and Python version.
- **Feature Requests:** Please open an issue to discuss the feature before writing code.
- **Pull Requests:** Ensure your code is formatted and follows the existing naming conventions.
