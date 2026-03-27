# /// script
# requires-python = ">=3.11"
# ///
"""Clone a git repository with optional worktree layout.

Usage:
    uv run clone.py <url> [<name>] [--workspace DIR]

If wt or git-wt is installed, creates a bare clone + worktree layout.
Otherwise, performs a standard git clone.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def detect_worktree_tool() -> bool:
    """Check if wt or git-wt is available."""
    return shutil.which("wt") is not None or shutil.which("git-wt") is not None


def repo_name_from_url(url: str) -> str:
    """Extract repo name from a git URL."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def clone_worktree(url: str, dest: Path) -> str:
    """Clone using bare repo + worktree layout. Returns default branch."""
    dest.mkdir(parents=True, exist_ok=True)
    bare = dest / ".bare"

    result = run(["git", "clone", "--bare", url, str(bare)])
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"git clone --bare failed")

    # Point .git at the bare repo
    (dest / ".git").write_text("gitdir: ./.bare\n")

    # Configure fetch refspec
    run(["git", "-C", str(bare), "config", "remote.origin.fetch",
         "+refs/heads/*:refs/remotes/origin/*"])
    run(["git", "-C", str(bare), "fetch", "origin"])

    # Detect default branch
    result = run(["git", "-C", str(bare), "symbolic-ref",
                  "refs/remotes/origin/HEAD"])
    if result.returncode == 0 and result.stdout.strip():
        branch = result.stdout.strip().replace("refs/remotes/origin/", "")
    else:
        branch = "master"

    # Create worktree
    run(["git", "worktree", "add", branch, branch], cwd=dest)
    return branch


def clone_standard(url: str, dest: Path) -> None:
    """Clone using standard git clone."""
    result = run(["git", "clone", url, str(dest)])
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"git clone failed")


def main():
    parser = argparse.ArgumentParser(description="Clone a git repository with optional worktree layout")
    parser.add_argument("url", help="Git clone URL")
    parser.add_argument("name", nargs="?", default=None, help="Directory name (default: derived from URL)")
    parser.add_argument("--workspace", "-w", default=os.environ.get("OSDU_WORKSPACE", os.getcwd()),
                        help="Workspace directory (default: $OSDU_WORKSPACE or cwd)")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    name = args.name or repo_name_from_url(args.url)
    dest = workspace / name
    use_worktree = detect_worktree_tool()

    method = "bare clone + worktree" if use_worktree else "standard clone"
    print(f"Repo:      {name}")
    print(f"URL:       {args.url}")
    print(f"Workspace: {workspace}")
    print(f"Method:    {method}")
    print()

    if dest.exists():
        print(f"SKIP  {name} (already exists)")
        return

    try:
        if use_worktree:
            branch = clone_worktree(args.url, dest)
            print(f"CLONE {name}")
            print()
            print(f"  {name}/")
            print(f"    .bare/       <- bare clone")
            print(f"    .git         <- pointer file")
            print(f"    {branch}/    <- worktree (ready to work in)")
        else:
            clone_standard(args.url, dest)
            print(f"CLONE {name}")
    except RuntimeError:
        print(f"FAIL  {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
