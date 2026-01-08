import ast
import os
from typing import Set


def get_imports(file_path: str) -> Set[str]:
    """Parse a python file and return a set of imported module names (internal only)."""
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def analyze_src(src_dir: str):
    print("graph TD")
    package_name = "claude_memory"

    # Map file paths to module names
    file_map = {}
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, src_dir)
                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                if module_name.startswith(package_name) or "dashboard" in module_name:
                    file_map[full_path] = module_name

    # Analyze imports
    for file_path, module in file_map.items():
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=file_path)
            except SyntaxError:
                continue

        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:  # Relative import
                    # resolve relative import
                    # module is e.g. claude_memory.tools
                    parts = module.split(".")
                    # remove 'level' number of parts from end
                    base = parts[: -node.level]
                    if node.module:
                        base.append(node.module)
                    target = ".".join(base)
                elif node.module:
                    target = node.module

            if target:
                # Check if target matches any known module
                for known_path, known_module in file_map.items():
                    if target == known_module:
                        if module != known_module:
                            print(f"    {module} --> {known_module}")


if __name__ == "__main__":
    src_path = os.path.join(os.path.dirname(__file__), "..", "src")
    analyze_src(src_path)
