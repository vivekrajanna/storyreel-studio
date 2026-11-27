"""Safe asset resolution and caching for StoryReel Studio."""

import shutil
from pathlib import Path
from typing import List, Tuple


def _find_existing_asset(base_path: Path) -> Path:
    """Return existing asset path, also checking .svg/.png/.jpg variants cleanly."""
    if base_path.is_file():
        return base_path
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
        alt = base_path.with_suffix(ext)
        if alt.is_file():
            return alt
    return base_path


def resolve_scene_image(
    image_ref: str,
    slug: str,
    project_root: Path,
    out_assets_dir: Path,
    fallback_path: Path,
) -> Tuple[str, bool]:
    """Copy a scene image into output/<slug>/assets/ and return (relative_url, used_fallback)."""
    out_assets_dir.mkdir(parents=True, exist_ok=True)
    candidates: List[Path] = []
    if image_ref:
        safe_ref = Path(image_ref)
        # Prevent path traversal outside project root
        if not safe_ref.is_absolute() and ".." not in safe_ref.parts:
            candidates.append(_find_existing_asset(project_root / "assets" / slug / safe_ref))
            candidates.append(_find_existing_asset(project_root / safe_ref))
            candidates.append(_find_existing_asset(project_root / "assets" / safe_ref))

    for cand in candidates:
        if cand.is_file():
            dest = out_assets_dir / cand.name
            if not dest.exists() or dest.stat().st_mtime < cand.stat().st_mtime:
                shutil.copy2(cand, dest)
            return f"assets/{dest.name}", False

    dest = out_assets_dir / fallback_path.name
    if not dest.exists() and fallback_path.is_file():
        shutil.copy2(fallback_path, dest)
    return f"assets/{dest.name}", True
