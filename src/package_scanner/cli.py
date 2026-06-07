import json
import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import typer
import duckdb
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
import httpx
from dotenv import load_dotenv

app = typer.Typer(help="CLI app to process package-scanner data")
console = Console()

DATA_FILE = Path("data/channel_v3.json")
DB_FILE = Path("data/registry.db")
REGISTRY_URL = "https://packagecontrol.io/channel_v3.json"

@app.command()
def sync():
    """Update the registry file and store in DuckDB."""
    console.print(f"Downloading {REGISTRY_URL}...")
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with httpx.stream("GET", REGISTRY_URL, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Downloading...", total=total or None)
            with open(DATA_FILE, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
                    
    console.print("Processing JSON and loading into DuckDB...")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    packages = data.get("packages_cache", {})
    records = []
    for repo_url, pkgs in packages.items():
        if not pkgs: continue
        for pkg in pkgs:
            name = pkg.get("name", "")
            homepage = pkg.get("homepage", "")
            releases = pkg.get("releases", [])
            latest_date = max([r.get("date", "") for r in releases]) if releases else None
            records.append((name, repo_url, homepage, latest_date))
            
    with duckdb.connect(str(DB_FILE)) as conn:
        conn.execute("DROP TABLE IF EXISTS packages")
        conn.execute("""
            CREATE TABLE packages (
                name VARCHAR,
                repo_url VARCHAR,
                homepage VARCHAR,
                latest_release_date VARCHAR,
                num_stars INTEGER
            )
        """)
        conn.executemany("""
            INSERT INTO packages (name, repo_url, homepage, latest_release_date)
            VALUES (?, ?, ?, ?)
        """, records)
        
    console.print("[green]Registry updated and loaded into DuckDB successfully![/green]")

def fetch_stars_for_repo(repo_url: str, owner_repo: str):
    """Fetch stars for a single repo using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", owner_repo, "--json", "stargazerCount", "--jq", ".stargazerCount"],
            capture_output=True, text=True, check=True
        )
        stars_count = int(result.stdout.strip())
        return repo_url, stars_count
    except Exception:
        return repo_url, None

@app.command()
def stars():
    """Use `gh` to get num_stars for every GitHub URL; show progress when processing."""
    load_dotenv()
    
    if not DB_FILE.exists():
        console.print("[red]Database file not found. Run 'sync' first.[/red]")
        raise typer.Exit(1)
        
    with duckdb.connect(str(DB_FILE)) as conn:
        rows = conn.execute("SELECT DISTINCT repo_url, homepage FROM packages").fetchall()
        
        # Collect github repos
        repos = {}
        for repo_url, homepage in rows:
            target_url = None
            if "github.com/" in str(repo_url):
                target_url = str(repo_url)
            elif homepage and "github.com/" in str(homepage):
                target_url = str(homepage)
                    
            if target_url:
                parts = target_url.split("github.com/")[-1].split("/")
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1].split(".git")[0].split("#")[0].split("?")[0]
                    if owner and repo:
                        repos[repo_url] = f"{owner}/{repo}"

        if not repos:
            console.print("No GitHub repositories found.")
            return

        console.print(f"Found {len(repos)} GitHub repositories. Fetching stars...")

        updates = []
        # Fetch stars concurrently with Progress
        with Progress(console=console) as progress:
            task = progress.add_task("Fetching stars...", total=len(repos))
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {
                    executor.submit(fetch_stars_for_repo, r_url, owner_repo): r_url 
                    for r_url, owner_repo in repos.items()
                }
                
                for future in futures:
                    future.add_done_callback(lambda _: progress.update(task, advance=1))
                    
                for future in futures:
                    r_url, stars_count = future.result()
                    if stars_count is not None:
                        updates.append((stars_count, r_url))
                        
        if updates:
            conn.executemany("UPDATE packages SET num_stars = ? WHERE repo_url = ?", updates)
            
    console.print("[green]Finished fetching stars and updated DuckDB registry.[/green]")

@app.command()
def filter(
    date: str = typer.Option(None, help="Minimum date (e.g. 2020 or 2020-01-01)"),
    stars: int = typer.Option(None, help="Minimum number of stars"),
    output: Path = typer.Option(None, "--output", "-o", help="Path to save the output as a JSON file")
):
    """Filter the entire list by conditions: e.g. date > 2020 & num_stars > 100"""
    if not DB_FILE.exists():
        console.print("[red]Database file not found. Run 'sync' first.[/red]")
        raise typer.Exit(1)

    with duckdb.connect(str(DB_FILE)) as conn:
        query = "SELECT name, num_stars, latest_release_date, repo_url, homepage FROM packages WHERE 1=1"
        params = []
        
        if stars is not None:
            query += " AND num_stars >= ?"
            params.append(stars)
        if date is not None:
            query += " AND latest_release_date >= ?"
            params.append(date)
            
        results = conn.execute(query, params).fetchall()

    console.print(f"[bold green]Found {len(results)} packages matching the criteria.[/bold green]")
    
    json_results = []
    for name, num_stars, latest_date, repo_url, homepage in results:
        star_str = num_stars if num_stars is not None else "N/A"
        date_str = latest_date if latest_date is not None else "N/A"
        console.print(f"- [bold]{name}[/bold] (Stars: {star_str}, Latest Release: {date_str})")
        
        if output:
            json_results.append({
                "name": name,
                "num_stars": num_stars,
                "latest_release_date": latest_date,
                "repo_url": repo_url,
                "homepage": homepage
            })
            
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(json_results, f, indent=2, ensure_ascii=False)
        console.print(f"[bold blue]Results saved to {output}[/bold blue]")

if __name__ == "__main__":
    app()