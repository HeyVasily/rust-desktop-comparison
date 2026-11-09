#!/usr/bin/env python3
"""Record exact tracked source bytes; refuse a silently reformatted benchmark."""
import hashlib
import subprocess
from pathlib import Path


def main():
    output = Path("artifacts/build")
    output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    (output / "source-commit.txt").write_text(commit + "\n", encoding="utf-8")
    paths = subprocess.check_output(["git", "ls-files", "-z", "examples", "tools", ".github/workflows"], text=True).split("\0")
    hashes = [f"{hashlib.sha256(Path(path).read_bytes()).hexdigest()}  {path}" for path in sorted(filter(None, paths))]
    (output / "source-sha256.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    subprocess.run(["git", "diff", "HEAD", "--exit-code", "--", "examples", "tools", ".github/workflows"], check=True)


if __name__ == "__main__":
    main()
