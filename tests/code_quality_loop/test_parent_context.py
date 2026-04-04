"""Tests for parent_context.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
from parent_context import gather_external_context


def test_no_classes_returns_empty(tmp_path: Path) -> None:
    src = tmp_path / "child.py"
    src.write_text("x = 1\n")
    assert gather_external_context(src) == ""


def test_stdlib_parent_returns_empty(tmp_path: Path) -> None:
    src = tmp_path / "child.py"
    src.write_text("from threading import Thread\n\nclass Worker(Thread):\n    pass\n")
    assert gather_external_context(src) == ""


def test_extracts_init_and_overridden_method(tmp_path: Path) -> None:
    parent = tmp_path / "base.py"
    parent.write_text(
        "class Animal:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n"
        "\n"
        "    def speak(self):\n"
        "        return '...'\n"
        "\n"
        "    def sleep(self):\n"
        "        return 'zzz'\n"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "from base import Animal\n"
        "\n"
        "class Dog(Animal):\n"
        "    def speak(self):\n"
        "        return 'woof'\n"
    )
    result = gather_external_context(child)
    assert "class Animal" in result
    assert "__init__" in result
    assert "speak" in result
    # sleep is NOT overridden or called, so should not appear
    assert "sleep" not in result


def test_extracts_super_called_method(tmp_path: Path) -> None:
    parent = tmp_path / "base.py"
    parent.write_text(
        "class Base:\n"
        "    def __init__(self):\n"
        "        pass\n"
        "\n"
        "    def validate(self):\n"
        "        return True\n"
        "\n"
        "    def unused(self):\n"
        "        return 42\n"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "from base import Base\n"
        "\n"
        "class Child(Base):\n"
        "    def run(self):\n"
        "        if super().validate():\n"
        "            print('ok')\n"
    )
    result = gather_external_context(child)
    assert "validate" in result
    assert "__init__" in result
    assert "unused" not in result


def test_extracts_self_called_inherited_method(tmp_path: Path) -> None:
    parent = tmp_path / "base.py"
    parent.write_text(
        "class Base:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "    def other(self):\n"
        "        return 2\n"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "from base import Base\n"
        "\n"
        "class Child(Base):\n"
        "    def run(self):\n"
        "        return self.helper() + 10\n"
    )
    result = gather_external_context(child)
    assert "helper" in result
    assert "other" not in result


def test_relative_import(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "base.py").write_text(
        "class Base:\n"
        "    def __init__(self):\n"
        "        self.x = 0\n"
    )
    child = pkg / "child.py"
    child.write_text(
        "from .base import Base\n"
        "\n"
        "class Child(Base):\n"
        "    pass\n"
    )
    result = gather_external_context(child)
    assert "__init__" in result


def test_no_matching_parent_file_returns_empty(tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child.write_text(
        "from nonexistent import Foo\n"
        "\n"
        "class Bar(Foo):\n"
        "    pass\n"
    )
    assert gather_external_context(child) == ""


def test_syntax_error_source_returns_empty(tmp_path: Path) -> None:
    src = tmp_path / "broken.py"
    src.write_text("class Foo(:\n")
    assert gather_external_context(src) == ""


def test_context_header_and_footer(tmp_path: Path) -> None:
    parent = tmp_path / "base.py"
    parent.write_text(
        "class Base:\n"
        "    def __init__(self):\n"
        "        pass\n"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "from base import Base\n"
        "\n"
        "class Child(Base):\n"
        "    pass\n"
    )
    result = gather_external_context(child)
    assert result.startswith("--- CONTEXT FROM OTHER FILES")
    assert "--- END CONTEXT FROM OTHER FILES ---" in result


# --- Function context tests ---


def test_imported_function_included(tmp_path: Path) -> None:
    helpers = tmp_path / "helpers.py"
    helpers.write_text(
        "def compute(x):\n"
        "    return x * 2\n"
        "\n"
        "def unused_func():\n"
        "    return 0\n"
    )
    src = tmp_path / "main.py"
    src.write_text(
        "from helpers import compute\n"
        "\n"
        "result = compute(5)\n"
    )
    result = gather_external_context(src)
    assert "def compute(x):" in result
    assert "unused_func" not in result


def test_multiple_imported_functions(tmp_path: Path) -> None:
    utils = tmp_path / "utils.py"
    utils.write_text(
        "def foo():\n"
        "    return 1\n"
        "\n"
        "def bar():\n"
        "    return 2\n"
        "\n"
        "def baz():\n"
        "    return 3\n"
    )
    src = tmp_path / "main.py"
    src.write_text(
        "from utils import foo, bar, baz\n"
        "\n"
        "x = foo()\n"
        "y = bar()\n"
    )
    result = gather_external_context(src)
    assert "def foo():" in result
    assert "def bar():" in result
    # baz is imported but never called
    assert "baz" not in result


def test_imported_function_not_called_excluded(tmp_path: Path) -> None:
    helpers = tmp_path / "helpers.py"
    helpers.write_text(
        "def compute(x):\n"
        "    return x * 2\n"
    )
    src = tmp_path / "main.py"
    src.write_text(
        "from helpers import compute\n"
        "\n"
        "# imported but never called\n"
        "ref = compute\n"
    )
    result = gather_external_context(src)
    assert result == ""


def test_function_from_nonexistent_file_ignored(tmp_path: Path) -> None:
    src = tmp_path / "main.py"
    src.write_text(
        "from nonexistent import helper\n"
        "\n"
        "helper()\n"
    )
    assert gather_external_context(src) == ""


def test_function_and_parent_class_combined(tmp_path: Path) -> None:
    base = tmp_path / "base.py"
    base.write_text(
        "class Base:\n"
        "    def __init__(self):\n"
        "        pass\n"
    )
    helpers = tmp_path / "helpers.py"
    helpers.write_text(
        "def helper():\n"
        "    return 42\n"
    )
    src = tmp_path / "main.py"
    src.write_text(
        "from base import Base\n"
        "from helpers import helper\n"
        "\n"
        "class Child(Base):\n"
        "    def run(self):\n"
        "        return helper()\n"
    )
    result = gather_external_context(src)
    assert "class Base" in result
    assert "def helper():" in result


def test_relative_import_function(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "utils.py").write_text(
        "def do_stuff():\n"
        "    return True\n"
    )
    src = pkg / "main.py"
    src.write_text(
        "from .utils import do_stuff\n"
        "\n"
        "do_stuff()\n"
    )
    result = gather_external_context(src)
    assert "def do_stuff():" in result
