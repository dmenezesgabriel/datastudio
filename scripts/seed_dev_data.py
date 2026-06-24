"""Downloads development datasets and loads them into DuckDB.

Run once before starting development:
    uv run python scripts/seed_dev_data.py
"""

import sys
import urllib.request
from pathlib import Path

import duckdb

_DATASETS: list[tuple[str, str, str]] = [
    (
        "nyc_taxi",
        "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-04.parquet",
        "parquet",
    ),
    (
        "seattle_weather",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/seattle-weather.csv",
        "csv",
    ),
    (
        "movies",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/movies.json",
        "json",
    ),
    (
        "cars",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/cars.json",
        "json",
    ),
]

_LOAD_SQL: dict[str, str] = {
    "parquet": "SELECT * FROM read_parquet('{path}')",
    "csv": "SELECT * FROM read_csv_auto('{path}')",
    "json": "SELECT * FROM read_json_auto('{path}')",
}


def _download_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  already downloaded: {dest.name}")
        return
    print(f"  downloading {dest.name} ...", end=" ", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f"done ({dest.stat().st_size // 1024} KB)")


def _load_into_duckdb(
    conn: duckdb.DuckDBPyConnection, name: str, path: Path, fmt: str
) -> None:
    source = _LOAD_SQL[fmt].format(path=path)
    conn.execute(f"CREATE OR REPLACE TABLE {name} AS {source}")
    count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]  # type: ignore[index]
    print(f"  loaded {name}: {count:,} rows")


def seed(db_path: str = "./dev_data/datastudio.duckdb") -> None:
    """Downloads datasets and loads them into the DuckDB at db_path.

    Example:
        seed("./dev_data/datastudio.duckdb")
    """
    data_dir = Path(db_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading datasets...")
    local_files: list[tuple[str, Path, str]] = []
    for name, url, fmt in _DATASETS:
        ext = url.rsplit(".", 1)[-1]
        dest = data_dir / f"{name}.{ext}"
        _download_file(url, dest)
        local_files.append((name, dest, fmt))

    print("\nLoading into DuckDB...")
    with duckdb.connect(db_path) as conn:
        for name, path, fmt in local_files:
            _load_into_duckdb(conn, name, path, fmt)

    print(f"\nDone. Database: {db_path}")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "./dev_data/datastudio.duckdb"
    seed(db)
