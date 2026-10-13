"""Download the selected public Kaggle recipe dataset to the local data folder.

Install the optional downloader first:
    python -m pip install kagglehub
Then run:
    python download_dataset.py

The downloaded CSV is local-only and is not committed to Git.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = "wafaaelhusseini/extended-recipes-dataset-64k-dishes"
DEFAULT_OUTPUT = ROOT / "data" / "IndianFoodDataset.csv"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download Rasoi's recipe CSV from Kaggle.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Kaggle dataset owner/name")
    parser.add_argument("--csv-name", help="Choose a specific CSV filename if the dataset contains several")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destination CSV path")
    args = parser.parse_args(argv)

    try:
        import kagglehub
    except ImportError:
        print("KaggleHub is not installed. Run: python -m pip install kagglehub", file=sys.stderr)
        return 1

    try:
        downloaded = Path(kagglehub.dataset_download(args.dataset))
    except Exception as exc:
        print(
            "Kaggle download failed. Check internet access, dataset availability, and any Kaggle authentication requirements.\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 1

    csv_files = sorted(path for path in downloaded.rglob("*.csv") if path.is_file())
    if not csv_files:
        print(f"No CSV files found in downloaded dataset directory: {downloaded}", file=sys.stderr)
        return 1

    if args.csv_name:
        candidates = [path for path in csv_files if path.name.casefold() == args.csv_name.casefold()]
        if len(candidates) != 1:
            print(
                f"Could not uniquely find CSV named {args.csv_name!r}. Available files:\n"
                + "\n".join(str(path) for path in csv_files),
                file=sys.stderr,
            )
            return 1
        selected = candidates[0]
    elif len(csv_files) == 1:
        selected = csv_files[0]
    else:
        print(
            "The dataset contains multiple CSV files. Choose one with --csv-name:\n"
            + "\n".join(path.name for path in csv_files),
            file=sys.stderr,
        )
        return 2

    args.output = args.output.expanduser().resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if selected.resolve() != args.output:
        shutil.copy2(selected, args.output)

    print(f"Kaggle dataset directory: {downloaded}")
    print(f"Selected CSV: {selected}")
    print(f"Rasoi CSV path: {args.output}")
    print("Next: inspect the CSV headers, then run python import_dataset.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
