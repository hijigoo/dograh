"""Build an owned SDK source copy with the committed CPU optimization patches."""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
MARKER = ".dograh-patches.json"


def digest(path: Path) -> str:
    """Return the source fingerprint used by the patch provenance manifest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(source: Path) -> dict[str, str]:
    """Fingerprint Python sources without recording interpreter cache files."""
    return {
        str(path.relative_to(source)): digest(path)
        for path in sorted((source / "src").rglob("*.py"))
    }


def prepare(source: Path, destination: Path, patches: Path) -> dict:
    """Apply a verified patch stack without editing the pinned Git submodule.

    Rebuild only a previously generated, unedited destination. Preserve unexpected
    destination contents by failing before any replacement.
    """
    source, destination, patches = (
        source.resolve(),
        destination.absolute(),
        patches.resolve(),
    )
    if destination.is_symlink():
        raise ValueError(f"Refusing a symlink destination: {destination}")
    destination = destination.resolve()
    if (
        source == destination
        or source in destination.parents
        or destination in source.parents
    ):
        raise ValueError(
            "The generated SDK must be separate from the source and its ancestors"
        )
    expected = json.loads((patches / "source.json").read_text(encoding="utf-8"))
    for relative, sha256 in expected["sha256"].items():
        path = source / relative
        if not path.is_file() or digest(path) != sha256:
            raise ValueError(
                f"Unsupported Pipecat source: {relative}; restore submodule "
                f"{expected['commit']} or review and regenerate the CPU patches"
            )
    stack = sorted(patches.glob("*.patch"))
    if not stack:
        raise ValueError(f"No CPU optimization patches found in {patches}")
    selected = {patch.name: digest(patch) for patch in stack}
    previous = None
    if destination.exists():
        marker = destination / MARKER
        if not marker.is_file():
            raise ValueError(
                f"Refusing to overwrite an unmanaged SDK directory: {destination}"
            )
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if source_hashes(destination) != previous["output_sha256"]:
            raise ValueError(
                f"Generated SDK has local source edits; preserve them before rebuilding: {destination}"
            )
        if previous.get("format_version") == 1 and previous["patch_sha256"] == selected:
            return previous
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".pipecat-build-", dir=destination.parent
    ) as temporary:
        working = Path(temporary) / "sdk"
        shutil.copytree(
            source,
            working,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "venv", "__pycache__", "build", "dist"
            ),
        )
        for patch in stack:
            command = [
                "git",
                "apply",
                "--no-index",
                "--unidiff-zero",
                "--whitespace=error",
            ]
            environment = os.environ | {"GIT_CEILING_DIRECTORIES": str(working.parent)}
            before = source_hashes(working)
            subprocess.run(
                [*command, "--check", str(patch)],
                cwd=working,
                env=environment,
                check=True,
            )
            subprocess.run(
                [*command, str(patch)], cwd=working, env=environment, check=True
            )
            if source_hashes(working) == before:
                raise RuntimeError(f"Patch did not modify SDK sources: {patch.name}")
        result = {
            "format_version": 1,
            "source_commit": expected["commit"],
            "source_sha256": expected["sha256"],
            "patch_sha256": selected,
            "output_sha256": source_hashes(working),
        }
        (working / MARKER).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        # Keep host editable-install SCM identity; Docker sources already use fallback_version.
        git_file = source / ".git"
        if git_file.is_file():
            reference = git_file.read_text(encoding="utf-8").strip()
            if reference.startswith("gitdir: "):
                git_directory = (source / reference.removeprefix("gitdir: ")).resolve()
                if git_directory.is_dir():
                    (working / ".git").write_text(
                        f"gitdir: {git_directory}\n", encoding="utf-8"
                    )
        if previous is not None:
            if source_hashes(destination) != previous["output_sha256"]:
                raise ValueError(
                    "Generated SDK changed during preparation; not replacing it"
                )
            destination.rename(Path(temporary) / "previous-sdk")
        working.rename(destination)
    logger.info("Prepared Pipecat with %s", ", ".join(selected))
    return result


def create_parser() -> argparse.ArgumentParser:
    """Define installation paths shared by Docker, CI and local development."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "pipecat")
    parser.add_argument("--destination", type=Path, default=ROOT / ".pipecat-optimized")
    parser.add_argument("--patches", type=Path, default=ROOT / "patches/pipecat")
    return parser


def main() -> int:
    """Prepare SDK sources and report unsupported versions as installation failures."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    arguments = create_parser().parse_args()
    prepare(arguments.source, arguments.destination, arguments.patches)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
