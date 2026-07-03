"""Architectural guard: no demo-dataset identity may leak into ``src/``.

DataStudio is a generative BI tool that must stay agnostic to the data it displays.
Concrete dataset identity (table/column names, domain values) belongs only to the
dev seed (``scripts/seed_dev_data.py``), the eval/test fixtures (``test/``), and the
sample data (``dev_data/``) — never to the shipped source under ``src/``, and never
to a prompt the model receives (e.g. ``catalog_prompt.generated.txt``).

This fails fast if a known identifier from the sample datasets (Olist e-commerce,
NYC taxi, Seattle weather, Vega movies/cars) reappears anywhere in ``src/``.
"""

import re
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_SCANNED_SUFFIXES = frozenset({".py", ".txt"})

# High-signal identifiers unique to the demo datasets. Word boundaries guard the
# ambiguous English words (e.g. "movies") so ordinary prose never trips the check.
_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"nyc_taxi",
    r"tpep_",
    r"olist",
    r"seattle_weather",
    r"order_count",
    r"Miles_per_Gallon",
    r"product_category_name",
    r"health_beauty",
    r"Warner Bros",
    r"Rotten Tomatoes",
    r"\brevenue\b",
    r"\bmovies\b",
    r"\bfilms\b",
)


def _scanned_files() -> list[Path]:
    """Return every source file under ``src/`` whose suffix is worth scanning."""
    return [
        path for path in _SRC_ROOT.rglob("*") if path.suffix in _SCANNED_SUFFIXES and path.is_file()
    ]


def _leaks_in(path: Path) -> list[str]:
    """Return the forbidden patterns found in one file (empty when clean)."""
    text = path.read_text(encoding="utf-8")
    return [p for p in _FORBIDDEN_PATTERNS if re.search(p, text, re.IGNORECASE)]


class TestNoDatasetIdentityInSrc:
    def test_src_names_no_demo_dataset_identifier(self) -> None:
        # Arrange
        files = _scanned_files()

        # Act
        offenders = {
            str(path.relative_to(_SRC_ROOT)): leaks for path in files if (leaks := _leaks_in(path))
        }

        # Assert
        assert offenders == {}, (
            "Demo-dataset identity leaked into src/ (keep it in scripts/seed_dev_data.py, "
            f"test/, or dev_data/): {offenders}"
        )
