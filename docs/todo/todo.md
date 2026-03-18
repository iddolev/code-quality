# To do list

## Remember

1. Really need to read all the documentation to see all the parts
   and I write a summary and then ask LLM to check if I missed anything,
   and before I start ask it to give a summary to help me get a hold of everything
2. there is also /simplify of claude code!
   "Review your recently changed files for code reuse, quality, and efficiency issues, then fix them. Spawns three review agents in parallel, aggregates their findings, and applies fixes. Pass text to focus on specific concerns: /simplify focus on memory efficiency"
   (https://code.claude.com/docs/en/skills)
3. "Custom commands have been merged into skills. A file at .claude/commands/deploy.md and a skill at .claude/skills/deploy/SKILL.md both create /deploy and work the same way. Your existing .claude/commands/ files keep working. 
   Skills add optional features: a directory for supporting files, frontmatter to control whether you or Claude invokes them, and the ability for Claude to load them automatically when relevant."
   (https://code.claude.com/docs/en/skills)
4. "Claude Code skills follow the Agent Skills open standard, which works across multiple AI tools. Claude Code extends the standard with additional features like invocation control, subagent execution, and dynamic context injection."
    (https://code.claude.com/docs/en/skills)

## Steps

1. Look at more tools below to see if to add
2. LSP server - can / should we use it instead of / in addition to the approach here?

# More tools

semgrep — pattern-based analysis with semantic understanding. It's like grep but understands Python's AST, so foo(x=bar) and foo(bar) can match the same rule. The community rulesets (p/python, p/owasp-top-ten) catch things Bandit misses, especially around injection patterns and framework-specific issues (Django, Flask, FastAPI). It's also the tool you'd use to write custom rules for your own codebase patterns.

coverage (with --branch) — measures which lines and branches your tests exercise. Not a code quality linter per se, but you can run it in the suite as a gate: "does this file have test coverage above X%?"

interrogate — docstring coverage as a percentage. Ruff's D rules flag missing docstrings per-item, but interrogate gives you a single number ("72% of public functions have docstrings") which is useful as a metric/gate. Lightweight and fast.

pyupgrade — automatically upgrades old Python syntax to modern equivalents (old-style formatting → f-strings, Optional[X] → X | None, removing # coding: utf-8, etc.). Ruff subsumes most of its rules via the UP ruleset, so if you're running Ruff you probably don't need this separately. But worth knowing it exists if you use Ruff with a narrow rule selection.

import-linter — enforces architectural layering rules like "module A must not import from module B" or "only the api layer can import from db." Very basic but nothing else does this in Python. You define contracts in a config file.

wily — tracks complexity metrics over time using git history. Not a per-file linter — it generates trend reports showing whether your codebase is getting more or less complex per commit. Useful for long-running projects.

mutmut — mutation testing. It modifies your code (flips > to >=, changes True to False, deletes lines) and checks if your tests catch the change. Extremely slow but finds tests that pass by coincidence. Not something you'd run per-file in a quick quality pass, but powerful for critical code.

fixit (Meta) — an autofixer framework built on libCST. Comes with some built-in rules and lets you write custom lint rules that can auto-fix while preserving formatting. More modern than Pylint's fixer and safer because it uses CST (concrete syntax tree) rather than AST, so comments and whitespace are preserved.

Dependabot is a GitHub-native service that monitors your repository's dependency files (across many ecosystems — Python, JS, Ruby, Go, etc.) and automatically opens pull requests when it detects a vulnerable dependency or when a newer version is available. It runs continuously in the background, so you don't have to remember to audit manually. It's free for public and private repos on GitHub.

Snyk is a commercial security platform (with a free tier) that goes broader than the others. It scans dependencies like the rest, but also does container image scanning, infrastructure-as-code analysis (Terraform, CloudFormation), and even static application security testing (SAST) on your own code. It integrates with GitHub, GitLab, Bitbucket, CI/CD pipelines, and IDEs. The key differentiator is that Snyk maintains its own curated vulnerability database with additional context like exploit maturity and fix guidance.

The mental model is roughly: pip-audit and npm audit are point-in-time CLI checks you run during development or CI. Dependabot is continuous monitoring with automated PRs. Snyk is an enterprise security platform that wraps dependency scanning into a much larger security posture story. They're not mutually exclusive — many teams use Dependabot for automated PRs and pip-audit/npm audit as a CI gate, with Snyk layered on top if the organization needs broader coverage.

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
