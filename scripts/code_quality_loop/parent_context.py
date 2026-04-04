"""Gather external context for the critic.

When the file under review contains a class that inherits from a
user-defined parent in another file, this module extracts the relevant
parts of the parent (constructor + overridden/used methods) so the
critic has enough context to review the child class properly.

It also extracts definitions of functions imported from other user files
that are called in the file under review.
"""
from __future__ import annotations

import ast
from pathlib import Path


def gather_external_context(source_path: Path) -> str:
    """Return a context block with parent class and imported function snippets, or ''."""
    source_code = source_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return ""

    import_map = _build_import_map(tree)
    source_dir = source_path.parent

    context_parts: list[str] = []
    context_parts.extend(_gather_parent_class_parts(tree, import_map, source_dir))
    context_parts.extend(_gather_function_parts(tree, import_map, source_dir))

    if not context_parts:
        return ""
    return (
        "--- CONTEXT FROM OTHER FILES (for reviewer reference only) ---\n\n"
        + "\n\n".join(context_parts)
        + "\n\n--- END CONTEXT FROM OTHER FILES ---\n\n"
    )


def _gather_parent_class_parts(tree: ast.Module, import_map: dict,
                                source_dir: Path) -> list[str]:
    """Gather context snippets for parent classes defined in other user files."""
    parts: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = base.id if isinstance(base, ast.Name) else None
            if not base_name or base_name not in import_map:
                continue

            module, level = import_map[base_name]
            parent_file = _resolve_local_module(source_dir, module, level)
            if not parent_file:
                continue

            child_method_names = _get_method_names(node)
            called_names = _find_called_methods(node)
            relevant_needed = child_method_names | called_names | {"__init__"}

            snippet = _extract_parent_snippet(parent_file, base_name, relevant_needed)
            if snippet:
                rel = _try_relative(parent_file, source_dir)
                parts.append(f"# From {rel}, class {base_name}:\n\n{snippet}")
    return parts


def _gather_function_parts(tree: ast.Module, import_map: dict,
                           source_dir: Path) -> list[str]:
    """Gather context snippets for functions imported from other user files."""
    called_names = _find_all_called_names(tree)

    # Group called imported names by resolved file
    file_to_names: dict[Path, list[str]] = {}
    for name in sorted(called_names):
        if name not in import_map:
            continue
        module, level = import_map[name]
        resolved = _resolve_local_module(source_dir, module, level)
        if not resolved:
            continue
        file_to_names.setdefault(resolved, []).append(name)

    parts: list[str] = []
    for file_path, names in file_to_names.items():
        snippet = _extract_function_snippets(file_path, set(names))
        if snippet:
            rel = _try_relative(file_path, source_dir)
            parts.append(f"# From {rel}:\n\n{snippet}")
    return parts


def _find_all_called_names(tree: ast.Module) -> set[str]:
    """Find all names directly called as functions anywhere in the module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def _extract_function_snippets(file_path: Path, names: set[str]) -> str:
    """Extract top-level function definitions matching names from a file."""
    source = file_path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    snippets: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names):
            end_line = node.end_lineno or node.lineno
            func_src = "\n".join(source_lines[node.lineno - 1 : end_line])
            snippets.append(func_src)

    return "\n\n".join(snippets)


def _build_import_map(tree: ast.Module) -> dict[str, tuple[str | None, int]]:
    """Map imported names to (module_string, import_level)."""
    result: dict[str, tuple[str | None, int]] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                result[alias.asname or alias.name] = (node.module, node.level)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result[alias.asname or alias.name] = (alias.name, 0)
    return result


def _resolve_local_module(source_dir: Path, module: str | None,
                          level: int) -> Path | None:
    """Try to resolve a module name to a local .py file. Return None if not found."""
    if level > 0:
        # Relative import: go up (level - 1) directories from source_dir
        base = source_dir
        for _ in range(level - 1):
            base = base.parent
        if not module:
            return None  # bare `from . import X` where X is a module — skip
        parts = module.replace(".", "/")
        candidate = base / f"{parts}.py"
    else:
        if not module:
            return None
        parts = module.replace(".", "/")
        # Try source_dir first, then walk up to find a project root
        # where the full module path resolves (handles absolute imports
        # like `from scripts.format_markdown.module import Class`).
        for base in _ancestors(source_dir):
            found = _try_as_file_or_package(base / f"{parts}.py")
            if found:
                return found
        return None

    return _try_as_file_or_package(candidate)


def _ancestors(directory: Path):
    """Yield directory itself, then each parent up to (and including) the root."""
    current = directory
    while True:
        yield current
        parent = current.parent
        if parent == current:
            break
        current = parent


def _try_as_file_or_package(candidate: Path) -> Path | None:
    """Return resolved path if candidate is a .py file or a package __init__."""
    if candidate.is_file():
        return candidate.resolve()
    pkg = candidate.with_suffix("") / "__init__.py"
    if pkg.is_file():
        return pkg.resolve()
    return None


def _get_method_names(class_node: ast.ClassDef) -> set[str]:
    """Get direct method names defined in a class (not nested classes)."""
    return {
        node.name
        for node in ast.iter_child_nodes(class_node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _find_called_methods(class_node: ast.ClassDef) -> set[str]:
    """Find method names called via self.X() or super().X() in the class body."""
    names: set[str] = set()
    for node in ast.walk(class_node):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        value = node.func.value
        # self.method(...)
        if isinstance(value, ast.Name) and value.id == "self":
            names.add(node.func.attr)
        # super().method(...)
        if (isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "super"):
            names.add(node.func.attr)
    return names


def _extract_parent_snippet(parent_file: Path, class_name: str,
                            relevant_methods: set[str]) -> str:
    """Extract constructor + relevant methods from a parent class."""
    source = parent_file.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    # Find the target class
    parent_class: ast.ClassDef | None = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            parent_class = node
            break
    if parent_class is None:
        return ""

    # Collect matching methods, preserving source order
    method_snippets: list[str] = []
    for child in ast.iter_child_nodes(parent_class):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if child.name not in relevant_methods:
            continue
        end_line = child.end_lineno or child.lineno
        method_src = "\n".join(source_lines[child.lineno - 1 : end_line])
        method_snippets.append(method_src)

    if not method_snippets:
        return ""

    # Build snippet: class signature + relevant methods
    class_line = source_lines[parent_class.lineno - 1]
    parts = ["    # ... (only relevant methods shown)"]
    parts.extend(method_snippets)
    joined = "\n\n".join(parts)
    return f'{class_line}\n{joined}'


def _try_relative(path: Path, base: Path) -> str:
    """Try to make path relative to base, fall back to file name."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return path.name
