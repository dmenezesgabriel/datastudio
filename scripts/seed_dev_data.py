"""Downloads development datasets and loads them into DuckDB.

Run once before starting development:
    uv run python scripts/seed_dev_data.py

Skip Kaggle datasets (no credentials needed):
    uv run python scripts/seed_dev_data.py --skip-kaggle
"""

import argparse
import base64
import io
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb
from pydantic_settings import BaseSettings, SettingsConfigDict


class SeedSettings(BaseSettings):
    """Dev-only settings for the seed script — not part of the application config.

    Example:
        settings = SeedSettings()
        print(settings.kaggle_username)
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    kaggle_username: str | None = None
    kaggle_key: str | None = None


@dataclass(frozen=True)
class PublicDataset:
    name: str
    url: str
    fmt: Literal["parquet", "csv", "json"]


@dataclass(frozen=True)
class KaggleDataset:
    slug: str  # e.g. "olistbr/brazilian-ecommerce"
    files: list[tuple[str, str]]  # (filename_inside_zip, duckdb_table_name)


_PUBLIC_DATASETS: list[PublicDataset] = [
    PublicDataset(
        "nyc_taxi",
        "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-04.parquet",
        "parquet",
    ),
    PublicDataset(
        "seattle_weather",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/seattle-weather.csv",
        "csv",
    ),
    PublicDataset(
        "movies",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/movies.json",
        "json",
    ),
    PublicDataset(
        "cars",
        "https://raw.githubusercontent.com/vega/vega-datasets/main/data/cars.json",
        "json",
    ),
]

_KAGGLE_DATASETS: list[KaggleDataset] = [
    KaggleDataset(
        slug="olistbr/brazilian-ecommerce",
        files=[
            ("olist_customers_dataset.csv", "olist_customers"),
            ("olist_geolocation_dataset.csv", "olist_geolocation"),
            ("olist_order_items_dataset.csv", "olist_order_items"),
            ("olist_order_payments_dataset.csv", "olist_order_payments"),
            ("olist_order_reviews_dataset.csv", "olist_order_reviews"),
            ("olist_orders_dataset.csv", "olist_orders"),
            ("olist_products_dataset.csv", "olist_products"),
            ("olist_sellers_dataset.csv", "olist_sellers"),
            ("product_category_name_translation.csv", "olist_category_translation"),
        ],
    ),
]

_READ_SQL: dict[str, str] = {
    "parquet": "SELECT * FROM read_parquet('{path}')",
    "csv": "SELECT * FROM read_csv_auto('{path}')",
    "json": "SELECT * FROM read_json_auto('{path}')",
}


class KaggleClient:
    """Authenticated Kaggle API client for downloading dataset zips.

    Example:
        client = KaggleClient(username="me", api_key="abc123")
        zip_bytes = client.download_zip("olistbr/brazilian-ecommerce")
    """

    _BASE_URL = "https://www.kaggle.com/api/v1/datasets/download"

    def __init__(self, username: str, api_key: str) -> None:
        token = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        self._auth_header = {"Authorization": f"Basic {token}"}

    def download_zip(self, dataset_slug: str) -> bytes:
        """Downloads a dataset zip from the Kaggle API and returns its raw bytes."""
        url = f"{self._BASE_URL}/{dataset_slug}"
        print(f"  downloading {dataset_slug} from Kaggle ...", end=" ", flush=True)
        request = urllib.request.Request(url, headers=self._auth_header)
        with urllib.request.urlopen(request) as response:
            data = response.read()
        print(f"done ({len(data) // 1024} KB)")
        return data


def _download_public_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  already downloaded: {dest.name}")
        return
    print(f"  downloading {dest.name} ...", end=" ", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f"done ({dest.stat().st_size // 1024} KB)")


def _load_table(conn: duckdb.DuckDBPyConnection, name: str, source_sql: str) -> None:
    conn.execute(f"CREATE OR REPLACE TABLE {name} AS {source_sql}")
    count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]  # type: ignore[index]
    print(f"  loaded {name}: {count:,} rows")


def _seed_public(
    conn: duckdb.DuckDBPyConnection,
    data_dir: Path,
    datasets: list[PublicDataset],
) -> None:
    print("Downloading public datasets...")
    for ds in datasets:
        ext = ds.url.rsplit(".", 1)[-1]
        dest = data_dir / f"{ds.name}.{ext}"
        _download_public_file(ds.url, dest)
        source_sql = _READ_SQL[ds.fmt].format(path=dest)
        _load_table(conn, ds.name, source_sql)


def _seed_kaggle(
    conn: duckdb.DuckDBPyConnection,
    data_dir: Path,
    client: KaggleClient,
    datasets: list[KaggleDataset],
) -> None:
    print("Downloading Kaggle datasets...")
    for ds in datasets:
        dataset_dir = data_dir / ds.slug.replace("/", "_")
        already_local = all((dataset_dir / csv).exists() for csv, _ in ds.files)

        if already_local:
            print(f"  already downloaded: {ds.slug}")
            zip_bytes = None
        else:
            dataset_dir.mkdir(parents=True, exist_ok=True)
            zip_bytes = client.download_zip(ds.slug)

        for csv_name, table_name in ds.files:
            dest = dataset_dir / csv_name
            if not dest.exists() and zip_bytes is not None:
                with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                    z.extract(csv_name, path=dataset_dir)
            source_sql = _READ_SQL["csv"].format(path=dest)
            _load_table(conn, table_name, source_sql)


def seed(
    db_path: str = "./dev_data/datastudio.duckdb",
    *,
    skip_public: bool = False,
    skip_kaggle: bool = False,
) -> None:
    """Downloads datasets and loads them into the DuckDB at db_path.

    Example:
        seed("./dev_data/datastudio.duckdb", skip_kaggle=True)
    """
    data_dir = Path(db_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(db_path) as conn:
        if not skip_public:
            _seed_public(conn, data_dir, _PUBLIC_DATASETS)

        if not skip_kaggle:
            settings = SeedSettings()
            if settings.kaggle_username is None or settings.kaggle_key is None:
                print(
                    "Warning: KAGGLE_USERNAME or KAGGLE_KEY not set — skipping Kaggle datasets."
                )
            else:
                client = KaggleClient(settings.kaggle_username, settings.kaggle_key)
                _seed_kaggle(conn, data_dir, client, _KAGGLE_DATASETS)

    print(f"\nDone. Database: {db_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download development datasets and load them into DuckDB."
    )
    parser.add_argument(
        "--db-path",
        default="./dev_data/datastudio.duckdb",
        help="DuckDB file path (default: ./dev_data/datastudio.duckdb)",
    )
    parser.add_argument(
        "--skip-public",
        action="store_true",
        help="Skip public HTTP datasets (NYC taxi, Seattle weather, movies, cars)",
    )
    parser.add_argument(
        "--skip-kaggle",
        action="store_true",
        help="Skip Kaggle datasets (requires KAGGLE_USERNAME and KAGGLE_KEY)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    seed(args.db_path, skip_public=args.skip_public, skip_kaggle=args.skip_kaggle)
