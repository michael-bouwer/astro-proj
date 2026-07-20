"""Writes a synthetic lights/darks/flats/biases dataset to disk for manual testing.

Useful when you want to exercise the pipeline or API against a real dataset
directory without owning a telescope: same frame generator the pytest suite
uses (tests/conftest.py), just pointed at a directory of your choosing.

Usage:
    python scripts/make_synthetic_dataset.py --output SyntheticDataset
    python scripts/make_synthetic_dataset.py --output SyntheticDataset --lights 10 --calibration 8
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.conftest import write_dataset  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Dataset directory to create (relative to repo root)")
    parser.add_argument("--lights", type=int, default=6, help="Number of light frames (default: 6)")
    parser.add_argument("--calibration", type=int, default=6, help="Number of bias/dark/flat frames each (default: 6)")
    args = parser.parse_args()

    output_dir = Path(__file__).resolve().parent.parent / args.output
    write_dataset(output_dir, num_lights=args.lights, num_calibration=args.calibration)
    print(f"Synthetic dataset written to {output_dir}")


if __name__ == "__main__":
    main()
