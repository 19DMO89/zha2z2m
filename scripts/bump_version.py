"""Set a new version in manifest.json and const.py.

Usage: python scripts/bump_version.py 0.2.0
Then add the changes to CHANGELOG.md, commit, and create the release:
    git tag v0.2.0 && git push --tags && gh release create v0.2.0 --generate-notes
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "zha2z2m"

version = sys.argv[1].removeprefix("v")
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    sys.exit("Version must look like 1.2.3")

manifest_path = ROOT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["version"] = version
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

const_path = ROOT / "const.py"
const = const_path.read_text(encoding="utf-8")
const_path.write_text(re.sub(r'^VERSION = ".*"$', f'VERSION = "{version}"', const, flags=re.M), encoding="utf-8")

print(f"Version set to {version}")
