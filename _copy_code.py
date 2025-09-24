#!/usr/bin/env python3
"""
Recursively scans the current directory to generate a project tree and
format file contents into a Markdown-style string. This is then copied
to the clipboard.

Excludes specified directories and files for a cleaner output.
It uses 'pbcopy' on macOS for robust clipboard support and 'pyperclip'
for other systems.
"""

import os
import sys
import subprocess

try:
    import pyperclip
except ImportError:
    pyperclip = None

# --- CONFIGURATION ---
# Add folder names you want to exclude from the scan.
EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "test-results",
    "__pycache__",
    ".git",
    ".vscode",
    ".idea",
    "dist",
    "build",
    ".pytest_cache",
}

# Add complete file names you want to exclude.
EXCLUDED_FILES = {
    ".env",
    "package-lock.json",
    "yarn.lock",
    # The script itself should be excluded
    os.path.basename(__file__),
}

# Add file extensions to exclude (binary files, logs, etc.).
EXCLUDED_EXTENSIONS = {
    ".log",
    ".db",
    ".sqlite3",
    ".lock",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".eot",
    ".ttf",
    ".otf",
    ".DS_Store",
}

# Mapping of file extensions to Markdown language identifiers.
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".md": "markdown",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    "dockerfile": "dockerfile",
}


# --- END OF CONFIGURATION ---


def get_language_identifier(filename):
    """Gets the Markdown language identifier for a given filename."""
    name_lower = filename.lower()
    if "." not in name_lower:
        return LANGUAGE_MAP.get(name_lower, "")
    _root, ext = os.path.splitext(name_lower)
    return LANGUAGE_MAP.get(ext, "")


def generate_tree(start_path, prefix=""):
    """Generates a tree-like string representation of the directory structure."""
    tree_lines = []
    # Get directory contents and filter out excluded items
    try:
        entries = sorted(os.listdir(start_path))
    except FileNotFoundError:
        return []

    filtered_entries = []
    for entry in entries:
        full_path = os.path.join(start_path, entry)
        if entry in EXCLUDED_DIRS or entry in EXCLUDED_FILES:
            continue
        _root, ext = os.path.splitext(entry)
        if ext.lower() in EXCLUDED_EXTENSIONS:
            continue
        filtered_entries.append(entry)

    for i, entry in enumerate(filtered_entries):
        connector = "└── " if i == len(filtered_entries) - 1 else "├── "
        tree_lines.append(f"{prefix}{connector}{entry}")

        full_path = os.path.join(start_path, entry)
        if os.path.isdir(full_path):
            extension = "    " if i == len(filtered_entries) - 1 else "│   "
            tree_lines.extend(generate_tree(full_path, prefix + extension))

    return tree_lines


def copy_to_clipboard(text: str):
    """Copies the given text to the system clipboard."""
    platform = sys.platform
    # 'darwin' is the platform name for macOS
    if platform == "darwin":
        try:
            process = subprocess.Popen(
                "pbcopy", env={"LANG": "en_US.UTF-8"}, stdin=subprocess.PIPE
            )
            process.communicate(text.encode("utf-8"))
            print("\n✅ Success! Copied to clipboard using pbcopy (macOS).")
        except FileNotFoundError:
            print("\n⚠️ 'pbcopy' command not found. Cannot copy to clipboard on macOS.")
    elif pyperclip:
        pyperclip.copy(text)
        print("\n✅ Success! Copied to clipboard using pyperclip.")
    else:
        print("\n⚠️ 'pyperclip' module not found and not on macOS.")
        print("Please install it with: pip install pyperclip")
        print("\nFull output will be printed below instead:\n")
        print("-" * 40)
        print(text)
        print("-" * 40)


def main():
    """Main function to generate tree, walk files, and copy to clipboard."""
    final_output_parts = []

    # 1. Generate the project tree
    print("Generating project tree...")
    tree_string = ".\n" + "\n".join(generate_tree("."))
    tree_block = f"# Project Tree\n```\n{tree_string}\n```\n\n"
    final_output_parts.append(tree_block)

    # 2. Walk through directories and read files
    print("Processing files...")
    for root, dirs, files in os.walk(".", topdown=True):
        # Efficiently exclude directories by modifying the list in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for filename in sorted(files):
            # Check against excluded files and extensions
            if filename in EXCLUDED_FILES:
                continue

            _root_ext, ext = os.path.splitext(filename)
            if ext.lower() in EXCLUDED_EXTENSIONS:
                continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.normpath(file_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if not content.strip():
                    continue

                lang = get_language_identifier(filename)

                file_block = f"# {relative_path}\n```{lang}\n{content}\n```\n\n"
                final_output_parts.append(file_block)
                print(f"  - Processed: {relative_path}")

            except Exception as e:
                print(f"  - Error reading file {file_path}: {e}")

    # 3. Assemble and copy to clipboard
    final_output = "".join(final_output_parts)

    if not final_output_parts:
        print("No files were processed. Nothing to copy.")
        return

    copy_to_clipboard(final_output)


if __name__ == "__main__":
    main()
