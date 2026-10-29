"""Create a portable source bundle; private documents are opt-in, runtime logs are excluded."""
import argparse
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--include-college-data", action="store_true")
parser.add_argument("--output", type=Path, default=Path("/tmp/academic-helpdesk-submission.zip"))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
excluded = {".venv", ".git", ".runtime", "__pycache__", ".pytest_cache", ".ruff_cache", "docs_for_assignment"}
with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.resolve() == args.output.resolve():
            continue
        if any(p in excluded or p.endswith(".egg-info") for p in relative.parts):
            continue
        if path.name == ".env" or path.suffix in {".pyc", ".zip"}:
            continue
        if path.name.startswith("unanswered") and path.suffix == ".csv":
            continue
        if relative.parts[:2] == ("data", "college") and not args.include_college_data:
            continue
        if relative.parts[:2] == ("reports", "runs"):
            continue
        bundle.write(path, relative)
print(args.output)
