#!/usr/bin/env python3
"""Unzip all archives from web_applications_zip into web_applications."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

SRC_DIR = Path("./data/WebTestBench/web_applications_zip")
OUT_DIR = Path("./data/WebTestBench/web_applications")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete conflicting extracted paths before unzipping.",
    )
    return parser.parse_args()


def get_top_level_members(zf: zipfile.ZipFile) -> set[str]:
    top_levels: set[str] = set()
    for info in zf.infolist():
        name = info.filename.strip("/")
        if not name:
            continue
        top_levels.add(name.split("/", 1)[0])
    return top_levels


def ensure_safe_path(base: Path, member_name: str) -> None:
    target = (base / member_name).resolve()
    base_resolved = base.resolve()
    if not str(target).startswith(str(base_resolved)):
        raise ValueError(f"Unsafe zip member path: {member_name}")


def safe_extract_all(zf: zipfile.ZipFile, out_dir: Path) -> None:
    for info in zf.infolist():
        ensure_safe_path(out_dir, info.filename)
    zf.extractall(out_dir)


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> None:
    args = parse_args()

    if not SRC_DIR.exists():
        raise FileNotFoundError(f"Source directory not found: {SRC_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    zip_files = sorted(p for p in SRC_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".zip")
    if not zip_files:
        print(f"No zip files found in: {SRC_DIR}")
        return

    extracted = 0
    skipped = 0
    failed = 0

    print(f"Source: {SRC_DIR}")
    print(f"Output: {OUT_DIR}")
    print(f"Zip files: {len(zip_files)}")

    for i, zip_path in enumerate(zip_files, start=1):
        print(f"[{i}/{len(zip_files)}] {zip_path.name}")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                top_levels = get_top_level_members(zf)
                conflicts = [name for name in sorted(top_levels) if (OUT_DIR / name).exists()]

                if conflicts and not args.overwrite:
                    print(f"  Skip (conflicts): {', '.join(conflicts[:3])}" + (" ..." if len(conflicts) > 3 else ""))
                    skipped += 1
                    continue

                if conflicts and args.overwrite:
                    for name in conflicts:
                        remove_path(OUT_DIR / name)
                    print(f"  Removed conflicts: {len(conflicts)}")

                safe_extract_all(zf, OUT_DIR)
                extracted += 1
                print("  Extracted")
        except Exception as exc:
            failed += 1
            print(f"  Failed: {exc}")

    print("\nDone")
    print(f"Extracted: {extracted}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")


if __name__ == "__main__":
    main()
