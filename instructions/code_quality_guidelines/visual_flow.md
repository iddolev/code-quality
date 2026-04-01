# Visual Flow Guidelines

## Purpose

This file contains basic guidelines for how to correctly structure a code file.
Although examples are shown in Python, the principles apply to any programming language.

## Critical Instructions:

<CRITICAL> 
The guidelines instruct about cosmetic/structural changes only! 
You must preserve the exact semantic behavior of the original code:
the output for a given input should remain the same.
If applying a guideline would require changing logic, control flow, return values, side effects, 
error handling behavior, or API contracts - do so very carefully.
</CRITICAL>

---

## Table of Contents

1. [Line Splits](#line-splits)
2. [Break Long/Complex Sections Into Smaller Blocks](#break-long-complex-sections-into-smaller-blocks)
3. [Avoid Deep Nesting](#avoid-deep-nesting)
4. [Keep `try` and `except` Close Together](#keep-try-and-except-close-together)

---

<a id="line-splits"/>

## Line Splits

Long lines should be split rather than allowing them to overflow beyond 100 characters. They should be split in logical places.

In particular, in the definition of a function and the call to a function that has many parameters,
put each parameter on a separate line. E.g.:

```python
def __init__(self,
             input_location: ResourceLocation,
             limit_number: int,
             relevant_sections: List[str],
             parallel_run: bool):
```

Another example:
When you have two "for" sections in a comprehension, put each on a separate line. E.g., instead of:

```python
[tuple(tokens[i:i + k]) for k in self.n_grams for i in range(1 + len(tokens) - k)]
```

write:

```python
[tuple(tokens[i:i + k])
 for k in self.n_grams
 for i in range(1 + len(tokens) - k)]
```

**Notice:** Automatic reformatting using PyCharm (Ctrl+Alt+L) sometimes splits lines in bad places, 
e.g. splits after an opening "[". So if you use PyCharm's reformatting, 
please go over the code and make sure lines are split in reasonable places.

<a id="break-long-complex-sections-into-smaller-blocks"/>

## Break Long/Complex Sections Into Smaller Blocks

Break large blocks by refactoring into smaller chunks:

Any code block, e.g. a function body, the body of a for/while loop, etc., 
must be no longer than 15 lines, to ease readability.
You can adhere to this rule by refactoring using shorter helper functions.

In fact, if the code block exceeds 10 lines, it should often be re-written 
to include the high-level algorithm of the block, 
which calls smaller helper functions, to make the code more readable.

<a id="avoid-deep-nesting"/>

## Avoid Deep Nesting

Nesting with more than 5 levels should be refactored because 
the code becomes difficult to read and maintain.

For example, consider this code:

```python
def get_cutoff(filepath: str):
    try:
        with open(filepath) as f:
            for line in f:
                <... a few more lines ...>
                m = re.match(r"last_updated:\s*(.*)", line)
                if m:
                    ts_str = m.group(1).strip()
                    if ts_str:
                        return parse_timestamp(ts_str)
    except FileNotFoundError:
        pass
    return None
```

There are 6 levels of nesting here, and it's visually disturbing.
A better way of writing this is:

```python
def _get_cutoff(f: File) -> Optional[datetime]:
    for line in f:
        <... a few more lines ...>
        m = re.match(r"last_updated:\s*(.*)", line)
        if m:
            ts_str = m.group(1).strip()
            if ts_str:
                return parse_timestamp(ts_str)
    return None

def get_cutoff(filepath: str) -> Optional[datetime]:
    try:
        with open(filepath) as f:
            return _get_cutoff(f)
    except FileNotFoundError:
        return None
```

Also: nested for-loops with 2 levels are often be more readable 
by refactoring the body of the outer loop to a separate function (with its own for-loop).

For example, instead of:

```python
def settle_accounts(ledgers):
    for ledger in ledgers:
        balance = 0
        for txn in ledger.transactions:
            if txn.is_void:
                continue
            balance += txn.amount
            if balance < 0:
                txn.flag_overdraft()
                balance += txn.penalty
        ledger.final_balance = balance
```

use:

```python
def _settle_ledger(ledger):
    balance = 0
    for txn in ledger.transactions:
        if txn.is_void:
            continue
        balance += txn.amount
        if balance < 0:
            txn.flag_overdraft()
            balance += txn.penalty
    ledger.final_balance = balance

def settle_accounts(ledgers):
    for ledger in ledgers:
        _settle_ledger(ledger)
```

<a id="keep-try-and-except-close-together"/>

## Keep `try` and `except` Close Together

The `except` clause handles an error that originates from a specific operation — typically the first line after `try:`. 
When a long block of code sits between `try:` and `except`, the reader loses sight of which operation 
the exception handler belongs to. It also risks catching exceptions that were thrown by unrelated code inside the block.

**Rule:** Keep the `try` block as short as possible. 
It should contain only the operation that can raise the exception (and any code that directly depends on it succeeding).
Move everything else outside the `try/except`.

For example, instead of:

```python
try:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.match(r"^version\s*:", line):
            new_line = f"version: {new_version}\n"
            if lines[i] == new_line:
                return
            lines[i] = new_line
            break
    else:
        return
    if dry_run:
        print(f"  [dry-run] Would update version in {INFO_FILE}")
    else:
        path.write_text("".join(lines), encoding="utf-8")
except OSError as e:
    warn(f"Could not update version in {INFO_FILE}: {e}")
```

Here, the `OSError` concern belongs with the file I/O, but it sits 15 lines away from `read_text`. The reader has to scan the entire block to understand what the `except` is guarding. Prefer:

```python
try:
    content = path.read_text(encoding="utf-8")
except OSError as e:
    warn(f"Could not read {INFO_FILE}: {e}")
    return
lines = content.splitlines(keepends=True)
for i, line in enumerate(lines):
    if re.match(r"^version\s*:", line):
        new_line = f"version: {new_version}\n"
        if lines[i] == new_line:
            return
        lines[i] = new_line
        break
else:
    return
if dry_run:
    print(f"  [dry-run] Would update version in {INFO_FILE}")
else:
    try:
        path.write_text("".join(lines), encoding="utf-8")
    except OSError as e:
        warn(f"Could not write {INFO_FILE}: {e}")
```

Now each `except` sits right next to the operation it guards, making the error-handling intent immediately clear.

<a id="use-class-members-instead-of-passing-values-around"/>

## Use class members instead of passing values around

This principles applies to a module having several functions that pass many values 
(function parameters) between themselves.
Sometimes such a case would benefit from encapsulating the functions as methods of a class 
which has private member variable that make it unnecessary to pass a lot of values around.

For example, suppose you are processing a list of log entries 
and need to track whether you are currently inside an error block 
(which spans multiple entries). 
You put the per-entry logic in a separate function according to the principle above:
"[Break Long/Complex Sections Into Smaller Blocks](#break-long-complex-sections-into-smaller-blocks)".
But the `inside_error_block` state carries across iterations. So instead of passing it back and forth:

```python
inside_error_block = False
for entry in log_entries:
    inside_error_block = process_entry(entry, inside_error_block)

def process_entry(entry: LogEntry, inside_error_block: bool) -> bool:
    ...   # code that may change the value of inside_error_block
    return inside_error_block
```

Consider encapsulating the state in a class:

```python
class LogProcessor:
    def __init__(self):
       self.inside_error_block = False

    def run(self, log_entries: List[LogEntry]):
        for entry in log_entries:
            self.process_entry(entry)

    def process_entry(self, entry: LogEntry) -> None:
        ...   # code that may change self.inside_error_block
```

Although in this example it may not be so obvious which approach is more readable,
we can say that the more you have values that are being passed around, 
the stronger the motivation to refactor the code to avoid a lot of passing around.

As another example, consider a function that loads data from several sources, 
then processes it in multiple steps — each step needing access to many of the loaded values:

```python
def run_next(source_path: Path) -> None:
    ip = issues_path(source_path)
    dp = decisions_path(source_path)
    issues = json.loads(ip.read_text(encoding="utf-8"))
    decisions = json.loads(dp.read_text(encoding="utf-8"))
    issues_by_id = {issue["id"]: issue for issue in issues}
    source_code = source_path.read_text(encoding="utf-8")
    client = Client()
    actionable = [d for d in decisions if d["status"] == "pending"]

    <... more code lines here ...>
    for decision in actionable:
        issue = issues_by_id[decision["id"]]
        verdict = check_relevance(source_code, issue, client)
        if verdict == "applicable":
            print(f"NEXT {issue}")
            return
        if verdict == "needs_update":
            issue.update(parse_updates(issue))
            ip.write_text(json.dumps(issues, indent=2), encoding="utf-8")
            print(f"NEXT {issue}")
            return
        decision["status"] = verdict
        dp.write_text(json.dumps(decisions, indent=2), encoding="utf-8")
    print("DONE")
```

This body is too long (>20 lines). But if you naively apply the rule
"[Break Long/Complex Sections Into Smaller Blocks](#break-long-complex-sections-into-smaller-blocks)", 
you face a problem: `issues`, `decisions`, `issues_by_id`, `source_code`, `ip`, `dp`, and `client` 
are all needed across steps. A naive helper function that loads them must return 4+ values:

```python
def _load_data(source_path, ip, dp):
    issues = json.loads(ip.read_text(encoding="utf-8"))
    decisions = json.loads(dp.read_text(encoding="utf-8"))
    issues_by_id = {issue["id"]: issue for issue in issues}
    source_code = source_path.read_text(encoding="utf-8")
    return issues, decisions, issues_by_id, source_code   # ← smell: 4 return values

def _process_decision(decision, issue, source_code, client,
                       issues, decisions, ip, dp, source_path):   # ← smell: 9 parameters
    ...
```

Returning 4 values and accepting 9 parameters are both signs that 
the refactoring traded one form of ugliness for another. 
The right solution here is a class, 
because all these variables belong together as the shared state of one coherent operation:

```python
class NextRunner:
    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.ip = issues_path(source_path)
        self.dp = decisions_path(source_path)
        self.issues = json.loads(self.ip.read_text(encoding="utf-8"))
        self.decisions = json.loads(self.dp.read_text(encoding="utf-8"))
        self.issues_by_id = {issue["id"]: issue for issue in self.issues}
        self.source_code = source_path.read_text(encoding="utf-8")
        self.client = Client()

    def run(self) -> None:
        actionable = [d for d in self.decisions if d["status"] == "pending"]
        for decision in actionable:
            if self._process_decision(decision):
                return
        print("DONE")

    def _process_decision(self, decision: dict) -> bool:
        issue = self.issues_by_id[decision["id"]]
        verdict = check_relevance(self.source_code, issue, self.client)
        if verdict in ("applicable", "needs_update"):
            if verdict == "needs_update":
                self._apply_update(issue)
            print(f"NEXT {issue}")
            return True
        decision["status"] = verdict
        self.dp.write_text(json.dumps(self.decisions, indent=2), encoding="utf-8")
        return False

    def _apply_update(self, issue: dict) -> None:
        issue.update(parse_updates(issue))
        self.ip.write_text(json.dumps(self.issues, indent=2), encoding="utf-8")
```

Now each method is short and reads clearly, with no multi-value returns or long parameter lists. 
The shared state (`issues`, `decisions`, `ip`, `dp`, etc.) lives in `self` where it belongs.

The key insight: **when "Break Long/Complex Sections" would force you 
to either return multiple values from a loader helper 
or pass many arguments to processing helper functions, 
that is a signal to use a class instead.**

**Caveat:** Use this pattern when the class represents at least a somewhat meaningful domain concept, 
not merely to avoid passing arguments. It's a judgement call: 
Wrapping unrelated variables in a class just to reduce function parameters 
may trade explicit data flow for hidden mutable state, 
which can make the code harder to reason about and debug.
