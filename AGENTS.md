# AI Agent Guidelines for subl-pkg-scanner

This document outlines the core architecture, rules, and conventions for AI assistants interacting with the `subl-pkg-scanner` repository.

## Project Context

`subl-pkg-scanner` is a Python CLI tool built to download, index, and query the Sublime Text Package Control registry (`channel_v3.json`). 
It maps package data into a local **DuckDB** instance, fetches live GitHub `stargazerCount` metrics via the **GitHub CLI (`gh`)**, and allows advanced filtering.

## Core Technologies

- **Dependency Management:** `uv`
- **CLI Framework:** `typer`
- **UI / Progress:** `rich`
- **Database:** `duckdb` (stored at `data/registry.db`)
- **HTTP Client:** `httpx` (used for streaming the registry JSON)
- **Environment:** `python-dotenv` (used to load `GH_TOKEN` from `.env`)

## Project Structure

```text
subl-pkg-scanner/
├── data/                       # Contains channel_v3.json and registry.db
├── src/
│   └── subl_pkg_scanner/
│       ├── __init__.py
│       └── cli.py              # Main Typer application and command definitions
├── tests/                      # Unit and integration tests
├── pyproject.toml              # uv configuration and entry point definition
└── README.md                   # Project documentation
```

## AI Development Rules

When modifying or extending this codebase, adhere to the following rules:

1. **Virtual Environment Management:**
   - Always rely on `uv` to manage the virtual environment. 
   - Execute commands using `uv run subl-pkg-scanner <command>`.
   - Add new dependencies using `uv add <package>`. Do not use `pip install`.

2. **DuckDB Interactions:**
   - Always connect using a context manager (`with duckdb.connect(str(DB_FILE)) as conn:`).
   - Use parameterized queries (`?`) to prevent SQL injection.
   - Batch insert/update operations using `conn.executemany` for performance.

3. **CLI / Subprocesses:**
   - Always use `subprocess.run(..., capture_output=True, text=True, check=True)` when invoking external tools like the `gh` CLI.
   - Ensure the `.env` file is loaded (`load_dotenv()`) before invoking `gh` commands, as `gh` utilizes the `GH_TOKEN`.
   - Limit concurrency using `ThreadPoolExecutor(max_workers=...)` to avoid spawning excessive subprocesses and hitting rate limits or OS limits.

4. **UI Conventions:**
   - Always use `rich.console.Console` for standard output instead of `print()`.
   - Use `rich.progress.Progress` for long-running tasks, ensuring UI responsiveness.

5. **File Operations:**
   - Use `pathlib.Path` for all file path operations. Ensure parent directories exist using `Path.parent.mkdir(parents=True, exist_ok=True)`.