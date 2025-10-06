# roxy

[![PyPI - Version](https://img.shields.io/pypi/v/roxy.svg)](https://pypi.org/project/roxy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/roxy.svg)](https://pypi.org/project/roxy)

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)
- [Developer Documentation](#developer-documentation)
  - [Required Tools](#required-tools)
  - [Project Setup](#project-setup)
  - [Useful Commands](#useful-commands)
- [Code Style](#code-style)

-----

## Installation

```sh
pip install roxy
```

-----

## License

`roxy` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

-----

## Developer Documentation

### Required Tools

- [Hatch](https://hatch.pypa.io/latest/install/#command-line-installer_1)

- after installation run: hatch config set dirs.env.virtual .hatch

### Project Setup

1. **Install dependencies and create your environment:**
   ```sh
   hatch run fix
   ```
   *Or run any other Hatch command; Hatch will install your environment automatically.*

2. **Activate the environment (Windows PowerShell):**
   ```sh
   .\.hatch\roxy\Scripts\activate.ps1
   ```

3. **Restart VS Code.**

4. **Select the Python interpreter:**
   - Press `Ctrl+Shift+P` → `Python: Select Interpreter`
   - Choose `('roxy': Hatch)` from the list.
   - If not visible, repeat step 2 or enter the interpreter path manually.

> **Note:**  
> Do **not** select `hatch-uv` as your environment—this is only used for installation.

-----

### Useful Commands

- **Show available environments:**
  ```sh
  hatch env show
  ```

- **Remove all environments (recommended over manual removal):**
  ```sh
  hatch env prune
  ```

- **Run pre-commit hooks and auto-fix code:**
  ```sh
  hatch run fix
  ```

-----

## Code Style

This project follows **PEP8** guidelines for Python code style.
To check and auto-fix code style issues, run:

```sh
hatch run fix
```
