# To do list

## Steps

1. Look at more tools below to see if to add
2. LSP server - can / should we use it instead of / in addition to the approach here?

# More tools

semgrep — pattern-based analysis with semantic understanding. It's like grep but understands Python's AST, so foo(x=bar) and foo(bar) can match the same rule. The community rulesets (p/python, p/owasp-top-ten) catch things Bandit misses, especially around injection patterns and framework-specific issues (Django, Flask, FastAPI). It's also the tool you'd use to write custom rules for your own codebase patterns.
deptry — finds dependency issues in your pyproject.toml or requirements.txt: packages you import but didn't declare, packages you declared but don't import, and transient dependencies you rely on directly (fragile because they could disappear if the intermediate package drops them).
pip-audit — checks your installed packages against known vulnerability databases (CVE, OSV). Different from Bandit: Bandit scans your code patterns, pip-audit scans your dependency versions. Both are needed.
Worth knowing about but more situational:
coverage (with --branch) — measures which lines and branches your tests exercise. Not a code quality linter per se, but you can run it in the suite as a gate: "does this file have test coverage above X%?"
interrogate — docstring coverage as a percentage. Ruff's D rules flag missing docstrings per-item, but interrogate gives you a single number ("72% of public functions have docstrings") which is useful as a metric/gate. Lightweight and fast.
pyupgrade — automatically upgrades old Python syntax to modern equivalents (old-style formatting → f-strings, Optional[X] → X | None, removing # coding: utf-8, etc.). Ruff subsumes most of its rules via the UP ruleset, so if you're running Ruff you probably don't need this separately. But worth knowing it exists if you use Ruff with a narrow rule selection.
import-linter — enforces architectural layering rules like "module A must not import from module B" or "only the api layer can import from db." Very basic but nothing else does this in Python. You define contracts in a config file.
wily — tracks complexity metrics over time using git history. Not a per-file linter — it generates trend reports showing whether your codebase is getting more or less complex per commit. Useful for long-running projects.
mutmut — mutation testing. It modifies your code (flips > to >=, changes True to False, deletes lines) and checks if your tests catch the change. Extremely slow but finds tests that pass by coincidence. Not something you'd run per-file in a quick quality pass, but powerful for critical code.
fixit (Meta) — an autofixer framework built on libCST. Comes with some built-in rules and lets you write custom lint rules that can auto-fix while preserving formatting. More modern than Pylint's fixer and safer because it uses CST (concrete syntax tree) rather than AST, so comments and whitespace are preserved.

### Not worth adding:

flake8 — fully subsumed by Ruff
pyflakes — subsumed by Ruff
pycodestyle — subsumed by Ruff
isort — subsumed by Ruff
autopep8 — subsumed by Ruff/Black
black — Ruff has a formatter now
pydocstyle — subsumed by Ruff's D rules
darglint — archived, partially covered by Ruff
xenon — just a threshold wrapper around Radon, you can do the same with radon cc -n C
pytype — useful but very slow and only works on Linux, overlaps heavily with mypy/pyright
cosmic-ray — mutation testing like mutmut but less maintained

# More cases

1. class members should be _ especially "variables"
2. instead of call_x, call_y, call_z (e.g. x, y, z are various LLM API proviers), use one call_provider(name: Provider)
   with Provider defines as an Enum of x, y, z
3. Refer to docs/todo/code_quality.py as a version with 2 arguments passing and instead would be cleaner to have a class :
   ```
   - passing them─through─every─function─is─noisy.A─cleaner─approach─would─be─a─small─class:

   Then run_tool, check_file, run_checks become methods on it, and self.log_file / self.missing_tools are just available — no need to thread them through every call 
   signature.

   The alternative — module-level globals — would also eliminate the passing but is harder to test and reason about. The class is the natural fit here since these   
   two pieces of state have the same lifetime (one run of the script) and are always used together.

   The QualityRunner class holds log_file and missing_tools as instance state, so no function needs to pass them around. _cmd_from_template and
   _collect_python_files became @staticmethod since they don't use instance state. main() is now just:

   runner = QualityRunner(log_file)
   runner.run(path)
   runner.write_missing_tools_summary()
   ```
4. instead of separated try ...long... except, refactor body to another function, so except is close by to try
   e.g. in the py file.
5. instead of func if cond long-body, do if not cond return then long-body, to reduce unnecessary indentation
   e.g.
   ```python
      def write_missing_tools_summary(self) -> None:
          """Write a summary of tools that were not found."""
          if self._missing_tools:
               self._log_file.write(f"{FILE_SEPARATOR} MISSING TOOLS SUMMARY {FILE_SEPARATOR}\n")
               for tool in sorted(set(self._missing_tools)):
                   self._log_file.write(f"  - {tool}\n")
               self._log_file.write("\n")
   ```
