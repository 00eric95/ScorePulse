# scripts/show_project_tree.py
from pathlib import Path
from datetime import datetime

# ────────────────────────────────────────────────
#          CONFIG - Change this to your project root
# ────────────────────────────────────────────────
PROJECT_ROOT = r"C:\Users\LENOVO\OneDrive\Desktop\SCORE_PULSEAIv2"

# Folders / files to completely ignore
IGNORE = {
    '__pycache__',
    '.pytest_cache',
    '.coverage',
    'htmlcov',
    'venv',
    '.venv',
    'env',
    'node_modules',
    '.git',
    '.idea',
    '.vscode',
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.log',           # optional - remove if you want to see logs
    'logs',            # optional
    'instance',        # optional
}

# File type icons (Unicode - works on Windows Terminal, PowerShell, most modern terminals)
ICONS = {
    'folder':       '📁 ',
    'templates':    '🗂️  ',    # special for templates folder
    'python':       '🐍 ',
    'html':         '🖼️ ',
    'css':          '🎨 ',
    'js':           '📜 ',
    'json':         '🔧 ',
    'csv':          '📊 ',
    'db':           '🗄️ ',
    'config':       '⚙️ ',
    'md':           '📝 ',
    'default':      '📄 '
}

def get_icon(path: Path) -> str:
    if path.is_dir():
        if path.name == "templates":
            return ICONS['templates']
        return ICONS['folder']
    
    suffix = path.suffix.lower()
    if suffix == '.py':
        return ICONS['python']
    elif suffix == '.html':
        return ICONS['html']
    elif suffix in ('.css', '.scss'):
        return ICONS['css']
    elif suffix in ('.js', '.ts'):
        return ICONS['js']
    elif suffix == '.json':
        return ICONS['json']
    elif suffix in ('.csv', '.tsv'):
        return ICONS['csv']
    elif suffix in ('.db', '.sqlite', '.sqlite3'):
        return ICONS['db']
    elif suffix in ('.yml', '.yaml', '.toml', '.ini'):
        return ICONS['config']
    elif suffix == '.md':
        return ICONS['md']
    else:
        return ICONS['default']

def print_project_tree(
    start_path: str = PROJECT_ROOT,
    max_depth: int = 7,
    highlight_templates: bool = True
):
    root = Path(start_path).resolve()

    if not root.exists():
        print(f"❌ Directory not found: {root}")
        return

    print(f"\nProject Tree — {root.name}")
    print(f"Location : {root}")
    print(f"Scanned  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("─" * 80 + "\n")

    def should_ignore(path: Path) -> bool:
        return any(ignored in path.parts or path.name == ignored for ignored in IGNORE)

    def _walk(current: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            print(prefix + "└── … (max depth)")
            return

        try:
            items = [p for p in current.iterdir() if not should_ignore(p)]
        except PermissionError:
            print(prefix + "└── [Permission denied]")
            return
        except Exception as e:
            print(prefix + f"└── [Error: {e}]")
            return

        items.sort(key=lambda p: (p.is_file(), p.name.lower()))

        if not items:
            print(prefix + "└── (empty)")
            return

        pointers = ["├── "] * (len(items) - 1) + ["└── "] if items else []

        for pointer, path in zip(pointers, items):
            is_last = pointer == "└── "
            icon = get_icon(path)
            name = path.name
            if path.is_dir():
                name += "/"

            # Highlight templates folder
            if highlight_templates and path.is_dir() and path.name == "templates":
                name = f"**{name}**  ← templates"

            print(f"{prefix}{pointer}{icon}{name}")

            if path.is_dir():
                extension = "│   " if not is_last else "    "
                _walk(path, prefix + extension, depth + 1)

    _walk(root)

    # Summary statistics
    print("\n" + "─" * 80)
    html_count = sum(1 for _ in root.rglob("*.html"))
    py_count   = sum(1 for _ in root.rglob("*.py"))
    js_count   = sum(1 for _ in root.rglob("*.js"))
    css_count  = sum(1 for _ in root.rglob("*.css"))
    json_count = sum(1 for _ in root.rglob("*.json"))
    db_count = sum(1 for p in root.rglob("*") if p.suffix.lower() in {'.db', '.sqlite', '.sqlite3'})

    print(f"Total .html files  : {html_count}")
    print(f"Total .py files    : {py_count}")
    print(f"Total .js files    : {js_count}")
    print(f"Total .css files   : {css_count}")
    print(f"Total .json files  : {json_count}")
    print(f"Total database files : {db_count}")
    print(f"Max depth scanned  : {max_depth}")
    print("Done ✓")


if __name__ == "__main__":
    print("Generating full project tree...\n")
    print_project_tree()