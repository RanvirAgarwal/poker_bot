"""
tools/export_review_bundle.py - Packages reviewable candidate release bundle.

Includes:
- Candidate sources (agent.py, runtime/)
- Opponent implementations (opponents/)
- Training and CFR audit sources (training/)
- Evaluation and scoring harnesses (evaluation/)
- Unit and regression test suites (tests/)
- Core configuration manifests and docker files (requirements.txt, docker/, tools/)
- Representative raw match JSON records (reports/raw_matches/)
- Reports and project memory (reports/, MEMORY.md, GEMINI.md, docs/)

Excludes large binary caches (.pkl > 10MB, .git, venv, __pycache__).
"""

from __future__ import annotations

import os
import sys
import zipfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(ROOT_DIR, "release")
os.makedirs(RELEASE_DIR, exist_ok=True)
BUNDLE_PATH = os.path.join(RELEASE_DIR, "review_bundle_RangeAware_v2.zip")


def should_include(rel_path: str) -> bool:
    # Exclude directories
    for ex in (".git", "venv", ".pytest_cache", "__pycache__"):
        if rel_path.startswith(ex + os.sep) or rel_path == ex:
            return False

    # Exclude large binary checkpoints > 5MB
    if rel_path.endswith(".pkl"):
        return False

    # Target specific directories and root files
    allowed_dirs = ("runtime", "opponents", "training", "evaluation", "tests", "docker", "tools", "docs", "reports")
    for d in allowed_dirs:
        if rel_path.startswith(d + os.sep):
            return True

    allowed_root_files = (
        "agent.py", "game.py", "evaluator.py", "judge_engine.py",
        "requirements.txt", "requirements-dev.txt", "pytest.ini",
        "MEMORY.md", "GEMINI.md", ".gitignore",
    )
    if rel_path in allowed_root_files:
        return True

    return False


def make_bundle():
    print(f"Creating review bundle at: {BUNDLE_PATH}")
    file_count = 0
    total_bytes = 0

    with zipfile.ZipFile(BUNDLE_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(ROOT_DIR):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, ROOT_DIR)
                if should_include(rel_path):
                    zipf.write(abs_path, arcname=rel_path)
                    file_count += 1
                    total_bytes += os.path.getsize(abs_path)

    mb_size = total_bytes / (1024 * 1024)
    zip_mb = os.path.getsize(BUNDLE_PATH) / (1024 * 1024)
    print(f"[OK] Bundled {file_count} files ({mb_size:.2f} MB uncompressed, {zip_mb:.2f} MB zip)")
    print(f"Destination: {BUNDLE_PATH}")
    return BUNDLE_PATH


if __name__ == "__main__":
    make_bundle()
