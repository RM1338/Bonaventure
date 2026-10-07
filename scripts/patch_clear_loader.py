"""Apply the DINOv2 download workaround to the separately cloned CLEAR source."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bonaventure.model_paths import CLEAR_CODE


def main():
    path = CLEAR_CODE / "src/clear/hub.py"
    source = path.read_text()
    if '"facebookresearch/dinov2:main"' in source and "skip_validation=True" in source:
        print("CLEAR download workaround already applied.")
        return
    repo = '"facebookresearch/dinov2",'
    trust = "        trust_repo=True,\n"
    if source.count(repo) != 1 or source.count(trust) != 1:
        raise RuntimeError(f"Unexpected CLEAR loader format: {path}; no changes made")
    source = source.replace(repo, '"facebookresearch/dinov2:main",')
    source = source.replace(trust, trust + "        skip_validation=True,\n")
    path.write_text(source)
    print(f"Applied CLEAR download workaround: {path}")


if __name__ == "__main__":
    main()
