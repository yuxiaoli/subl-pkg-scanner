# subl-pkg-scanner

A robust, blazing-fast CLI application designed to download, parse, and filter Sublime Text packages from the official Package Control registry (`channel_v3.json`). 

It leverages **DuckDB** for instantaneous querying, **Rich** for beautiful terminal outputs and progress bars, and the **GitHub CLI (`gh`)** to fetch live repository metrics concurrently.

## Features

- **Sync Registry**: Downloads the massive Sublime Text package registry and efficiently indexes it into a local DuckDB instance.
- **Fetch Stars**: Automatically extracts GitHub repository links from the packages and fetches their live `stargazerCount` using the `gh` CLI.
- **Advanced Filtering**: Quickly query the local database using SQL-powered filters (e.g., by release date or minimum star count).
- **JSON Export**: Export your filtered queries straight to JSON for programmatic consumption.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [GitHub CLI (`gh`)](https://cli.github.com/)
- A `.env` file containing your GitHub token (`GH_TOKEN=ghp_...`) for higher API rate limits.

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yuxiaoli/subl-pkg-scanner.git
   cd subl-pkg-scanner
   ```

2. **Sync the environment:**
   Ensure dependencies are installed and the `subl-pkg-scanner` executable is mapped.
   ```bash
   uv sync
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the project root and add your GitHub token.
   ```env
   GH_TOKEN=your_github_personal_access_token
   ```

## Usage

You can invoke the application using `uv run subl-pkg-scanner <command>`.

### 1. `sync`
Downloads the latest `channel_v3.json` from Package Control and loads all package metadata into a local `data/registry.db` DuckDB database.

```bash
uv run subl-pkg-scanner sync
```

### 2. `stars`
Scans the local DuckDB database for GitHub repositories and concurrently fetches the current star counts using the `gh` CLI. Make sure your `.env` is configured.

```bash
uv run subl-pkg-scanner stars
```

### 3. `filter`
Filters the cached package database based on specified criteria.

**Options:**
- `--date`: Minimum latest release date (e.g. `2020` or `2020-01-01`).
- `--stars`: Minimum number of stars the repository must have.
- `-o, --output`: Path to save the filtered output as a JSON file.

**Example:**
Find all packages updated since 2024 with more than 100 stars, and save them to `top_packages.json`.
```bash
uv run subl-pkg-scanner filter --date 2024 --stars 100 -o top_packages.json
```

## Architecture

- **`src/subl_pkg_scanner/cli.py`**: The primary entry point built with `typer`.
- **DuckDB**: Serves as the storage backend (`data/registry.db`), replacing raw JSON parsing for much faster filtering.
- **ThreadPoolExecutor**: Utilized in the `stars` command to spawn concurrent subprocesses to maximize the throughput of GitHub CLI requests.
