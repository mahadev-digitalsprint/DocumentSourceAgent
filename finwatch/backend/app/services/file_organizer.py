"""File organization helpers for placing docs into final folders."""
from __future__ import annotations

import shutil
from pathlib import Path


def target_subfolder(doc_type_field: str) -> str:
    value = (doc_type_field or "").upper()
    if "QUARTER" in value or "HALF_YEAR" in value or "INTERIM" in value:
        return "QuarterlyReports"
    if "ANNUAL" in value or "YEAR" in value:
        return "AnnualReports"
    if value.startswith("FINANCIAL|"):
        return "FinancialStatements"
    if value.startswith("NON_FINANCIAL|"):
        return "NonFinancial"
    return "Other"


def infer_base_folder(current_path: Path, company_slug: str, default_base: str) -> Path:
    slug_lower = (company_slug or "").lower()
    parts = list(current_path.parts)
    for index, part in enumerate(parts):
        if part.lower() == slug_lower and index > 0:
            return Path(*parts[:index])
    return Path(default_base)


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{stem}_v{counter}{suffix}")
        counter += 1
    return candidate


def move_to_classified_folder(
    *,
    local_path: str,
    company_slug: str,
    doc_type_field: str,
    default_base: str,
    copy_mode: bool = False,
) -> str:
    """
    Move/copy file into final folder based on classified doc type.

    copy_mode=True is used when multiple document rows share the same local_path.
    """
    if not local_path:
        return local_path

    source = Path(local_path)
    if not source.exists() or not source.is_file():
        return local_path

    base_folder = infer_base_folder(source, company_slug, default_base)
    destination_dir = base_folder / company_slug / target_subfolder(doc_type_field)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name

    try:
        if source.resolve() == destination.resolve():
            return str(source)
    except Exception:
        if str(source) == str(destination):
            return str(source)

    destination = _unique_path(destination)
    if copy_mode:
        shutil.copy2(str(source), str(destination))
    else:
        shutil.move(str(source), str(destination))
    return str(destination)
