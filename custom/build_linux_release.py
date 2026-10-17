#!/usr/bin/env python3
# Build a production Linux editor + export templates from a Godot source tree,
# and install the templates where the editor looks for them.
#
# Usage: custom/build_linux_release.py
#   Paths come from custom/.env (copy custom/.env.template and edit):
#     GODOT_SRC_DIR              Godot source tree to build
#     GODOT_TEMPLATES_DIR        export_templates root the editor reads from
#     COMPILE_JOBS               parallel compile jobs (empty: nproc - 2)
#     LINK_JOBS                  parallel GCC LTO link jobs, ~4.3 GB RAM each (empty: 2)
#   Relative paths are resolved against this script's directory.
#   Environment overrides:
#     COMPILE_JOBS=10            overrides COMPILE_JOBS from .env
#     LINK_JOBS=2                overrides LINK_JOBS from .env
#     GODOT_VERSION_STATUS=...   version suffix (default: braces), so these builds
#                                never clash with stock templates of the same version
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"


def load_env(path):
    if not path.is_file():
        sys.exit(f"Missing {path}: copy {path.name}.template to {path.name} and fill in the paths")
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            sys.exit(f"{path}: bad line: {line}")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def env_jobs(values, key, default):
    jobs = os.environ.get(key) or values.get(key) or str(default)
    if not jobs.isdigit() or int(jobs) < 1:
        sys.exit(f"{key} must be a positive integer, got {jobs!r}")
    return jobs


def env_path(values, key):
    if not values.get(key):
        sys.exit(f"{ENV_FILE}: {key} is not set")
    path = Path(os.path.expanduser(values[key]))
    return path if path.is_absolute() else (SCRIPT_DIR / path).resolve()


def main():
    values = load_env(ENV_FILE)
    src = env_path(values, "GODOT_SRC_DIR")
    templates_root = env_path(values, "GODOT_TEMPLATES_DIR")

    cpus = os.cpu_count() or 1
    compile_jobs = env_jobs(values, "COMPILE_JOBS", cpus - 2 if cpus > 2 else 1)
    link_jobs = env_jobs(values, "LINK_JOBS", 2)
    os.environ.setdefault("GODOT_VERSION_STATUS", "braces")
    status = os.environ["GODOT_VERSION_STATUS"]

    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=src,
                            capture_output=True, text=True).stdout.strip() or "no git"
    print(f"Source: {src} ({branch})")
    print(f"Jobs:   {compile_jobs} compile, {link_jobs} link")

    common = ["scons", "platform=linuxbsd", "arch=x86_64", "production=yes", f"-j{compile_jobs}", f"lto_jobs={link_jobs}"]
    for target in ("editor", "template_release", "template_debug"):
        subprocess.run(common + [f"target={target}"], cwd=src, check=True)

    # Template folder name must match the editor's version string, e.g. 4.7.2.braces
    sys.path.insert(0, str(src))
    import version
    patch = f".{version.patch}" if version.patch else ""
    ver = f"{version.major}.{version.minor}{patch}.{status}"

    dest = templates_root / ver
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "bin/godot.linuxbsd.template_release.x86_64", dest / "linux_release.x86_64")
    shutil.copy2(src / "bin/godot.linuxbsd.template_debug.x86_64", dest / "linux_debug.x86_64")
    (dest / "version.txt").write_text(ver + "\n")

    print()
    print(f"Editor:    {src}/bin/godot.linuxbsd.editor.x86_64")
    print(f"Templates: {dest}")


if __name__ == "__main__":
    main()
