# scripts/show_templates.py
from pathlib import Path
import os

def print_template_tree(
    start_path: str = r"C:\Users\LENOVO\OneDrive\Desktop\SCORE_PULSEAIv2\soccer_match_prediction\app\templates",
    max_depth: int = 5
):
    """
    Print a nice tree view of all .html (and other template files) in the templates folder.
    """
    root = Path(start_path).resolve()
    
    if not root.exists():
        print(f"❌ Directory not found: {root}")
        print("   Make sure the path is correct and accessible.")
        return
    
    if not root.is_dir():
        print(f"❌ Not a directory: {root}")
        return

    print(f"\nTemplate structure in:")
    print(f"  {root}\n")

    def _walk(current: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            print(prefix + "└── … (depth limit reached)")
            return

        # Get all items, sort directories first, then files
        items = sorted(
            current.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower())
        )

        if not items:
            print(prefix + "└── (empty)")
            return

        pointers = ["├── "] * (len(items) - 1) + ["└── "] if items else []

        for pointer, path in zip(pointers, items):
            is_last = pointer == "└── "
            name = path.name
            if path.is_dir():
                name += "/"

            print(f"{prefix}{pointer}{name}")

            if path.is_dir():
                extension = "│   " if not is_last else "    "
                _walk(path, prefix + extension, depth + 1)

    _walk(root)

    # Optional: also show total count of HTML files
    html_files = list(root.rglob("*.html"))
    print(f"\nTotal HTML templates found: {len(html_files)}")


if __name__ == "__main__":
    print("Scanning template folder...\n")
    print_template_tree()