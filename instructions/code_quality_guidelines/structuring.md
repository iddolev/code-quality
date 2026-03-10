---
author: Iddo Lev
last_update: 2026-03-09
---

# Correct Structuring

## Purpose

This file contains guidelines for how to correctly structure your code.
All guidelines are based on real cases observed in code that was
written by junior software engineers and could be improved.
Although examples are shown in Python, the principles apply to any programming language.

## Critutal Instructions for the LLM:

CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You must preserve the exact semantic behavior of the original code. 
If applying a guideline would require changing logic, control flow, return values, side effects, 
error handling behavior, or API contracts - suggest the improvement instead of actually doing it. 
When in doubt, leave the code unchanged, and ask the user.

## Table of Contents

1. [Basic Understanding](#basic-understanding)
   1. [Naming Conventions](#naming-conventions)
   2. [Avoid Magic Values](#avoid-magic-values)
   3. [Comments](#comments)
2. [Visual Flow](#visual-flow)
   1. [Line Splits](#line-splits)
   2. [Break Long/Complex Sections Into Smaller Blocks](#break-long-complex-sections-into-smaller-blocks)
   3. [Avoid Deep Nesting](#avoid-deep-nesting)
3. [Order](#order)
   1. [Put the smaller `if` case first](#put-the-smaller-if-case-first)
   2. [Order `if/elif` branches by likelihood](#order-ifelif-branches-by-likelihood)
   3. [Order methods and functions consistently](#order-methods-and-functions-consistently)
4. [Function Design](#function-design)
   1. [Limit the Number of Parameters](#limit-the-number-of-parameters)
   2. [Default Values](#default-values)
   3. [Avoid Boolean Flag Parameters](#avoid-boolean-flag-parameters)
   4. [Prefer Pure Functions](#prefer-pure-functions)
5. [End Cases](#end-cases)
6. [Don't Repeat Yourself](#don't-repeat-yourself)
   1. [Factor Out Conditional Differences](#factor-out-conditional-differences)
   2. [Use Polymorphism](#use-polymorphism)
7. [Utilities Instead of Code Idioms](#utilities-instead-of-code-idioms)
8. [Write Logic-Level / High-Level Code](#write-logic-level-high-level-code)
9. [Encapsulation](#encapsulation)
   1. [Put in a class](#put-in-a-class)
   2. [Information Hiding](#information-hiding)
   3. [Use class members instead of passing values around](#use-class-members-instead-of-passing-values-around)
10. [Single-Responsibility Principle](#single-responsibility-principle)
    1. [Separate Builder from Object](#separate-builder-from-object)
11. [More](#more)

<a id="basic-understanding"/>

## 1. Basic Understanding

<a id="naming-conventions"/>

### 1.1. Naming Conventions

Use consistent naming conventions throughout your codebase. Consistent naming makes code easier to read, search, and maintain.

Specifically in Python, follow the conventions defined in <a href="https://peps.python.org/pep-0008/#naming-conventions" target="_blank">PEP 8</a>:

| Element             | Convention       | Examples            |
|---------------------|------------------|---------------------|
| Files / modules     | `snake_case`     | `data_loader.py`    |
| Packages            | `lowercase`      | `mypackage`         |
| Variables           | `snake_case`     | `max_retries`       |
| Functions           | `snake_case`     | `calculate_score()` |
| Methods             | `snake_case`     | `get_user_name()`   |
| Classes             | `PascalCase`     | `DataProcessor`     |
| Constants           | `UPPER_SNAKE_CASE` | `MAX_BUFFER_SIZE`   |
| Type variables      | `PascalCase`     | `KeyType`, `T`      |
| Private members     | `_leading_underscore` | `_internal_cache`   |

Beyond following a convention table, keep these principles in mind:

1. **Be consistent across the codebase.** If one module calls it `user_id`, don't call it `userId` or `uid` elsewhere. Pick one term for each concept and stick with it.
2. **Use descriptive names.** A variable name should convey its purpose. Prefer `remaining_attempts` over `r` or `tmp`. Single-letter names are acceptable only for short-lived loop indices or well-known conventions (e.g. `i`, `x`, `df` in data-science code).
3. **Avoid abbreviations** unless they are universally understood in the domain (e.g. `url`, `html`, `db`). Prefer `configuration` over `cfg`, `message` over `msg`.
4. **Names should match their behavior.** A function named `get_X` indicates that it returns an object X of a relevant type. It’s bad practice to use this name for a function that calculates X (and e.g. puts it in a private class member) and returns `None`. Similarly, `clean_text(text: str) -> List[str]` is a bad name because it doesn’t tell us about the returned list. A correct name would be e.g. `clean_and_tokenize_text`.
5. **Pay attention to singular/plural names.** A variable containing a list of strings may be called `codes` but (usually) not `code`.
6. **Booleans should read as conditions.** Use prefixes like `is_`, `has_`, `should_`, or `can_` so that `if` statements read naturally, e.g. `if is_valid:` rather than `if valid:`.
7. **Function names should be actions, class names should be objects.** E.g. `handle_message` for a function, `MessageHandler` for a class.
8. **Don’t name a variable with a type that contradicts its content.** This is highly confusing. For example:

```python
line_elements = tokens[value.start_pos: value.end_pos + 1]
```

This variable should be called `line_tokens` because it holds `Token` objects, not `Element` objects.

<a id="avoid-magic-values"/>

### 1.2. Avoid Magic Values

A "<a href="https://en.wikipedia.org/wiki/Magic_number_(programming)" target="_blank">magic value</a>" is a literal number, string, or other value that appears directly in the code without explanation. "Magic values" make the code harder to read (the reader has to guess what the value means) and harder to maintain (if the value needs to change, you have to find every occurrence).

For example, instead of:

```python
if retries > 3:
    raise TimeoutError("too many retries")

time.sleep(86400)
```

define named constants:

```python
MAX_RETRIES = 3
SECONDS_IN_A_DAY = 86400

if retries > MAX_RETRIES:
    raise TimeoutError("too many retries")

time.sleep(SECONDS_IN_A_DAY)
```

The same applies to string literals. Instead of scattering `"pending"`, `"approved"`, `"rejected"` throughout the code, define them in one place (e.g. as constants, an `Enum`, or a dedicated class):

```python
class Status:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
```

In this way:

- It’s easier to find usages of the value by asking the IDE to show usages of the constant, instead of searching for the value itself.
- An in-place typo like `"aproved"` becomes impossible
- Your IDE can autocomplete the values and usages of the variable
- Renaming a status requires changing only one line.

<a id="comments"/>

### 1.3. Comments

It is a good practice to add a comment (starting with `#`) explaining a line or segment of code whose purpose or function may not be clear.

Place the comment on the line above the code, not at the end of the line. E.g., instead of:

```python
for key in d:  # comment explaining the loop
    do_something(key, d)
```

use:

```python
# comment explaining this
for key in d:
    do_something(key, d)
```

However, in conditional cases, add the explanation inside the case. E.g., instead of:

```python
if some_condition:  # comment explaining this case
    do_something
```

use:

```python
if some_condition:
    # comment explaining this case
    do_something
```

Additional guidelines:

1. **Comments should explain "why", not "what".** The code already shows what it does. A comment like `# increment counter` above `counter += 1` adds nothing. A comment like `# retry counter resets after a successful handshake` explains intent that the code alone cannot convey.
2. **Don't leave stale comments.** A wrong or outdated comment is worse than no comment. When you change code, update or remove the associated comments.
3. **TODOs should have context.** Write `# TODO(name): reason` rather than a bare `# TODO`. A TODO without context becomes permanent clutter that no one dares to remove.
4. **Use docstrings for functions and classes.** Describe the purpose, parameters, and return value. Docstrings are part of the interface (the programming language supports them) and are distinct from inline comments that explain implementation details. For example, in Python:

````python
def calculate_score(attempts: int, max_attempts: int) -> float:
    """
    Return a normalized score between 0 and 1 based on the number of attempts.

    :param attempts: The number of attempts made.
    :param max_attempts: The maximum allowed attempts.
    :return: A float where 1.0 means first-try success and 0.0 means all attempts used.
    """
    return max(0.0, 1 - attempts / max_attempts)
````

<a id="visual-flow"/>

## 2. Visual Flow

<a id="line-splits"/>

### 2.1. Line Splits

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

**Notice:** Automatic reformatting using PyCharm (Ctrl+Alt+L) sometimes splits lines in bad places, e.g. splits after an opening "[". So if you use it, please go over the code and make sure lines are split in appropriate places.

<a id="break-long-complex-sections-into-smaller-blocks"/>

### 2.2. Break Long/Complex Sections Into Smaller Blocks

Break large blocks by refactoring into smaller chunks:

1. A file, and a class, should be no longer than about 200 lines.
2. Any code block, e.g. a function, the body of a for/while loop, etc., should not be longer than 12-15 lines, to ease readability.

<a id="avoid-deep-nesting"/>

### 2.3. Avoid Deep Nesting

Avoid nesting with more than 2 or 3 levels, as it becomes unreadable, and difficult to maintain.

For example, consider this code:

```python
def get_cutoff():
    try:
        with open(EXPLANATIONS_FILE) as f:
            for line in f:
                m = re.match(r"last_updated:\s*(.*)", line)
                if m:
                    return parse_timestamp(m.group(1))
    except FileNotFoundError:
        pass
    return None
```

There are 5 levels of nesting here, and it's visually disturbing.
Also, the concern of `FileNotFoundError` belongs together with opening a file, and not several lines below it.
A better way of writing this is:

```python
def _get_cutoff(f: File) -> Optional[datetime]:
    for line in f:
        m = re.match(r"last_updated:\s*(.*)", line)
        if m:
            return parse_timestamp(m.group(1))
    return None

def get_cutoff(filepath: str) -> Optional[datetime]:
    try:
        with open(filepath) as f:
            return _get_cutoff(f)
    except FileNotFoundError:
        return None
```

Also often: nested for-loops with 2 levels would be more readable by extracting the body of the outer loop to a separate function (with its own for-loop).

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

<a id="order"/>

## 3. Order

<a id="put-the-smaller-if-case-first"/>

### 3.1. Put the smaller `if` case first

E.g. instead of

```python
def func(x):
    if some_condition(x):
        do_1(x)
        do_2(x)
        ... # long sequence of lines
        do_n(x)
    else:
       do_short(x) # short sequence of lines
    return x
```

Use:

```python
def func(x):
    if not some_condition(x):
        do_short(x)
        return x
    do_1(x)
    do_2(x)
    ... # long sequence of lines
    do_n(x)
    return x
```

This has less indentation, and is easier to debug.

<a id="order-ifelif-branches-by-likelihood"/>

### 3.2. Order `if/elif` branches by likelihood

When you have a chain of `if/elif` branches, put the most common case first. This makes the code easier to read because the reader encounters the typical path before the edge cases.

For example, suppose you are handling HTTP responses where the vast majority are successful. Instead of leading with rare error cases:

```python
def handle_response(status_code):
    if status_code == 401:
        reauthenticate()
    elif status_code == 403:
        raise PermissionError("forbidden")
    elif status_code == 404:
        raise LookupError("not found")
    elif status_code == 200:
        process_response()
    else:
        raise RuntimeError(f"unexpected status: {status_code}")
```

put the common case first:

```python
def handle_response(status_code):
    if status_code == 200:
        process_response()
    elif status_code == 401:
        reauthenticate()
    elif status_code == 403:
        raise PermissionError("forbidden")
    elif status_code == 404:
        raise LookupError("not found")
    else:
        raise RuntimeError(f"unexpected status: {status_code}")
```

Note: If this rule contradicts the previous rule [Put the smaller `if` case first](#put-the-smaller-if-case-first), then it's a judgment call: Prefer the previous rule if it's more pronounced.

<a id="order-methods-and-functions-consistently"/>

### 3.3. Order methods and functions consistently

Within a file or class, follow a consistent ordering convention so that readers know where to look:

1. **In a class:** put public methods before private (underscore-prefixed) methods. Within each group, a logical ordering (e.g. lifecycle order: `__init__`, then the main entry point, then helpers) is better than alphabetical.
2. **In a module:** define helper functions before the functions that call them (bottom-up), or after them (top-down) — but be consistent across the codebase. In Python, both styles work because functions are looked up at call time, not at definition time.

For example, instead of scattering helpers randomly:

```python
class ReportGenerator:
    def _format_header(self): ...
    def generate(self): ...
    def __init__(self, data): ...
    def _write_to_file(self, path): ...
```

organize by visibility and logical flow:

```python
class ReportGenerator:
    def __init__(self, data): ...
    def generate(self): ...
    def _format_header(self): ...
    def _write_to_file(self, path): ...
```

<a id="function-design"/>

## 4. Function Design

<a id="limit-the-number-of-parameters"/>

### 4.1. Limit the Number of Parameters

A function with many parameters is hard to read, call correctly, and maintain. As a rule of thumb, aim for **3 or fewer** parameters. When you find yourself adding a 4th or 5th parameter, consider grouping related parameters into a dataclass or configuration object.

For example, instead of:

```python
def send_report(title: str, recipient: str, cc: str, subject: str,
                body: str, attach_csv: bool, compress: bool):
    ...
```

define a config object:

```python
@dataclass
class ReportConfig:
    title: str
    recipient: str
    cc: str
    subject: str
    body: str
    attach_csv: bool = False
    compress: bool = False

def send_report(config: ReportConfig):
    ...
```

This makes call sites cleaner, and adding a new option in the future doesn't change the function signature.

<a id="default-values"/>

### 4.2. Default Values: Usually boolean default value should be False and not True

Usually it's bad practice to have a boolean parameter of a function have a default value of `True`,
because omitting the parameter silently enables a behavior that the caller might not be aware of.
See if you can rename the parameter to mean the opposite, with a default value of `False`.

For example, instead of:

```python
def save_report(report: Report, overwrite: bool = True):
    ...
```

Here, a caller who writes `save_report(report)` may not realize they are silently overwriting existing files. Prefer:

```python
def save_report(report: Report, keep_existing: bool = False):
    ...
```

Now the default behavior is the safer one (overwrite), and the caller must explicitly opt in to the alternative.

See also: [Avoid Boolean Flag Parameters](#avoid-boolean-flag-parameters) for cases where a boolean parameter should be eliminated entirely.

<a id="avoid-boolean-flag-parameters"/>

### 4.3. Avoid Boolean Flag Parameters

A boolean parameter that causes a function to do one of two substantially different things is a sign that the function should be split in two. The caller knows which branch they want, so make that explicit.

For example, instead of:

```python
def load_data(source: str, from_cache: bool):
    if from_cache:
        return _load_from_cache(source)
    else:
        return _load_from_disk(source)
```

expose two functions:

```python
def load_data_from_cache(source: str):
    return _load_from_cache(source)

def load_data_from_disk(source: str):
    return _load_from_disk(source)
```

This makes every call site self-documenting. The reader never has to look up what `True` or `False` means.

Note: this guideline applies when the boolean selects between **different behaviors**. A boolean that slightly modifies the same behavior (e.g. `verbose=True` adding log output) is fine. For booleans you do keep, see [Default Values](#default-values) for why the default should usually be `False`.

<a id="prefer-pure-functions"/>

### 4.4. Prefer Pure Functions

A <a href="https://en.wikipedia.org/wiki/Pure_function" target="_blank">pure function</a> is one whose return value depends only on its inputs and that has no side effects. Pure functions are easier to test, debug, and reason about.

For example, instead of:

```python
total = 0

def add_to_total(value: int):
    global total
    total += value
```

prefer:

```python
def compute_total(values: List[int]) -> int:
    return sum(values)
```

When side effects are necessary (I/O, logging, database writes), isolate them at the boundaries of your program and keep the core logic pure. That is, have thin outer functions that perform the I/O (reading a file, querying a database, writing output) and pass the resulting data into pure inner functions that contain the actual logic.

<a id="end-cases"/>

## 5. End Cases

Your code should handle all end cases. In particular:

1. Don't assume correct input. Check for it. Either:
   1. If an incorrect input may be encountered during runtime, check for it and, if needed, raise ValueError or some other appropriate Exception.
   2. If an incorrect input cannot be encountered during runtime but only during development, you can use `assert` to verify that this is true. Don't use assert statements to check for runtime errors - Python's `-O` flag strips all `assert` statements from the compiled bytecode, so they are not guaranteed to run in production.
2. Always end an `if`/`elif` chain with an `else` clause. If there is supposed to be no `else` case, raise `NotImplementedError()` to catch unexpected values. Skipping this is fragile: if a new case is introduced later, the function silently returns `None` instead of failing loudly.

For example, instead of:

```python
def get_permissions(role: str):
    if role == "admin":
        return ALL_PERMISSIONS
    elif role == "editor":
        return EDIT_PERMISSIONS
    elif role == "viewer":
        return VIEW_PERMISSIONS
```

Here, when a `"moderator"` role is added to the system later, this function silently returns `None`, which may cause bugs far from the source. Use:

```python
def get_permissions(role: str):
    if role == "admin":
        return ALL_PERMISSIONS
    elif role == "editor":
        return EDIT_PERMISSIONS
    elif role == "viewer":
        return VIEW_PERMISSIONS
    else:
        raise NotImplementedError(f"Unknown role: {role}")
```

Now, an unhandled role fails immediately with a clear message.

<a id="don't-repeat-yourself"/>

## 6. Don't Repeat Yourself

<a href="https://en.wikipedia.org/wiki/Don%27t_repeat_yourself" target="_blank">Don't Repeat Yourself</a> (DRY): If you see that two sections of code look very similar, factor out the common parts to a function, and call it twice with the different values.

<a id="factor-out-conditional-differences"/>

### 6.1. Factor Out Conditional Differences

Here is some code using DataFrames:

```python
if not some_cond:
    df[out] = df[column].apply(lambda x: x >= min_value and x < max_value) & df[out]
else:
    df[out] = df[column].apply(lambda x: x < min_value or x >= max_value) & df[out]
```

It can be simplified to:

```python
def in_range(x):
    return min_value <= x < max_value

modifier = df[column].apply(in_range)

if some_cond:
    modifier = ~modifier
df[out] &= modifier
```

The main idea demonstrated here: The two cases are very similar. The shared parts (i.e. applying a function on a column, modifying `df[out]`) are factored out and written just once.

**Tip:** The refactored code also demonstrates a few smaller improvements:

1. Instead of: `X >= Y and X < Z`, you can use: `Y <= X < Z`.
2. Instead of: `X = X op Y`, you can use: `X op= Y` (above: `df[out] &= modifier`).
3. Don't write the negation of a condition by yourself - let the code do it for you (above: `in_range` is written once, and the negation is calculated using `~`).

<a id="use-polymorphism"/>

### 6.2. Use Polymorphism

Here are three similar functions, where `NodeA`, `NodeB`, and `NodeC` are subclasses of `Node`.

```python
def foo_node_a(data: pd.DataFrame, node: NodeA):
    data[col] = data[data[col] == node.value]

def foo_node_b(data: pd.DataFrame, node: NodeB):
    data[col] = data[data[col].isin(node.values)]

def foo_node_c(data: pd.DataFrame, node: NodeC):
    data[col] = data[data[col] <= node.max_value]
```

How can we use DRY here? Factor out the common part, and move the different part to the specific node class:

```python
def foo_node(data: pd.DataFrame, node: Node):
    data[col] = data[data[col].apply(node.condition)]

class Node:
    def condition(self, x) -> bool:
        raise NotImplementedError()

class NodeA(Node):
    def condition(self, x) -> bool:
        return x == self.value

class NodeB(Node):
    def condition(self, x) -> bool:
        return x in self.values

class NodeC(Node):
    def condition(self, x) -> bool:
        return x <= self.max_value
```

Why is this better?

1. It separates the logic of the main procedure (`foo_node`) from the logic that differs between the classes.
2. In the future, if we add another child of `Node`, it will be easier to add just the part it does differently (the `condition` method).

<a id="utilities-instead-of-code-idioms"/>

## 7. Utilities Instead of Code Idioms

A "<a href="https://en.wikipedia.org/wiki/Programming_idiom" target="_blank">code idiom</a>" is a syntactic fragment that recurs frequently across software projects and has a single semantic role. For example, in Python, writing a string to a text file while ensuring the path exists:

```python
import os
import pathlib

folder_path = os.path.dirname(SOME_FILEPATH)
pathlib.Path(folder_path).mkdir(parents=True, exist_ok=True)
with open(SOME_FILEPATH, 'w') as f:
    f.write(SOME_TEXT)
```

Such "code idioms" should be avoided because it doesn't make sense that every place requiring this functionality will contain it from scratch. You can easily implement a utilities repository that wraps such low-level functions with logical operations, e.g.: `ensure_path`, `save_text_file`, `delete_path`, etc. Then the code looks cleaner:

```python
from utilities import ensure_folder_path, save_text_file

ensure_folder_path(os.path.dirname(SOME_FILEPATH))
save_text_file(SOME_FILEPATH, SOME_TEXT)
```

This idea is a special case of the general principle [Don't Repeat Yourself](#don't-repeat-yourself).

<a id="write-logic-level-high-level-code"/>

## 8. Write Logic-Level / High-Level Code

Python and other modern programming languages are very high-level and flexible, which means that a lot of the results you would like to achieve can be done using very succinct code that relies on high-level operations. Many such operations are already given to you in the programming language or in some existing library.

Here is an example of a good refactoring. Suppose you have a dictionary mapping from a line id to the line's list of elements, and you want to return a dictionary from a line id to the first largest element of the line's elements list. Each element has a start and end position, and the element's length is defined as: `1+end-start`.

The original code:

```python
found_matches = {}
for line, values in section.items():
    max_length_in_line = 0
    final_value = []
    for value in values:
        match_length = value.end_pos - value.start_pos
        if max_length_in_line <= match_length:
            max_length_in_line = match_length
            final_value = value
    found_matches[line] = final_value
return found_matches
```

In the above code, the reader needs to read it carefully to understand what it's doing.
Here's the refactored code:

```python
found_matches = {line_num: self.first_longest_element(values)
                 for line_num, values in section.items()}
```

In this code, you can easily see at a high-level the main thing the code is doing: applying `first_longest_element` on each value of the dict. So you clearly see the two main things going on here:
the algorithm (for-loop on a dict), and the inner operation (`first_longest_element`). Also, the operation has a descriptive name which clearly shows what it does. Now we add:

```python
def first_longest_element(values: List[TagElement]) -> TagElement:
    return max(values, key=TagElement.__len__)
```

Here, instead of doing this calculation using low-level operations (remembering the max value seen so far, comparing using `<=`, etc.), we use the high-level operator `max`. If we don't want `max` directly on the value, we can use the `key` argument and give it:
`lambda element: 1 + element.end_pos - element.start_pos`.
But that is too specific to be defined here - according to OOP, the property of an element (such as its length) should be defined in the class itself. So we add a `__len__` method to the TagElement class:

```python
class TagElement:
    ...
    def __len__(self) -> int:
        return 1 + self.end_pos - self.start_pos
```

<a id="encapsulation"/>

## 9. Encapsulation

Encapsulation is a basic principle of <a href="https://en.wikipedia.org/wiki/Object-oriented_programming" target="_blank">Object Oriented Programming</a> (OOP). Read about <a href="https://en.wikipedia.org/wiki/Encapsulation_(computer_programming)" target="_blank">encapsulation</a>, and related concepts: <a href="https://en.wikipedia.org/wiki/Coupling_(computer_programming)#Disadvantages_of_tight_coupling" target="_blank">disadvantages of tight coupling</a>, <a href="https://en.wikipedia.org/wiki/Information_hiding" target="_blank">information hiding</a>, <a href="https://en.wikipedia.org/wiki/Separation_of_concerns" target="_blank">separation of concerns</a>, <a href="https://en.wikipedia.org/wiki/Modular_design" target="_blank">modular design</a>.

The main idea is to put inside a class all members and methods that are relevant for the class, instead of spreading it around over different functions or places.

<a id="put-in-a-class"/>

### 9.1. Put in a class

**All queries about a class that depend only on the class content should be a method in the class**

Sometimes when we define a class, we don't yet define all methods that will be useful for that class. Don't take the current definition of the class as final, you can add new methods as needed.

For example, in a classical <a href="https://en.wikipedia.org/wiki/Natural_language_processing" target="_blank">NLP</a> parser, we may have a class `LexicalElement`, which is created when a `LexiconEntry` matches some sequence of words. `LexicalElement` contains a member `tokens: List[Token]`. At some point, we wanted to get the text which is obtained by concatenating the texts of the `tokens`.

The wrong way to do it is to rely on `line_tokens`, the entire list of tokens of the line where the `LexicalElement` was found, and use:

```python
' '.join([token.lower for token in
          line_tokens[element.start_pos: element.end_pos + 1]])
```

Instead, the moment you see that you need such a functionality, and realize that all the information is contained in the class, and that this functionality could be useful elsewhere, then add in `LexicalElement`:

```python
@property
def tokens_text(self) -> str:
    return ' '.join(token.lower for token in self.tokens)
```

and then simply use `element.tokens_text`.

<a id="information-hiding"/>

### 9.2. Information Hiding

<a href="https://en.wikipedia.org/wiki/Information_hiding" target="_blank">Information Hiding</a> is the principle of segregating the design decisions of a piece of code that are most likely to change, thus protecting other parts of the program from extensive modification if the design decision is changed. The protection involves providing a stable *interface* which protects the remainder of the program from the implementation.

**Don't access private members**

For example, class `Foo` contains a member `dc` which is a dict.

Instead of accessing this member directly:

```python
x = Foo(...)
y = x.dc.get(value)
```

define an accessor:

```python
class Foo:
    def __init__(self):
       self._dc: Dict[KeyType, ValueType] = {}

    def get_value(self, key: KeyType) -> Optional[ValueType]:
        return self._dc.get(key)

x = Foo(...)
y = x.get_value(value)
```

Note: To protect Foo from misuse, name the dictionary member `_dc`, using the Python [convention](#TBD-link): an underscore `_` prefix indicates a private member.

Even more crucial is avoiding assigning a value to a member of a class.
Instead of:

```python
X.dc = value
```

use:

```python
x.set_dc(value)
```

<a id="use-class-members-instead-of-passing-values-around"/>

### 9.3. Use class members instead of passing values around

For example, suppose you are processing a list of log entries and need to track whether you are currently inside an error block (which spans multiple entries). You put the per-entry logic in a separate function according to the principle "[Break Long/Complex Sections Into Smaller Blocks](#break-long-complex-sections-into-smaller-blocks)".
But the `inside_error_block` state carries across iterations. So instead of passing it back and forth:

```python
inside_error_block = False
for entry in log_entries:
    inside_error_block = process_entry(entry, inside_error_block)

def process_entry(entry: LogEntry, inside_error_block: bool) -> bool:
    ...   # code that may change inside_error_block
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

**Caveat:** Use this pattern when the class represents a meaningful domain concept, not merely to avoid passing arguments. Wrapping unrelated variables in a class just to reduce function parameters trades explicit data flow for hidden mutable state, which can make the code harder to reason about and debug.

<a id="single-responsibility-principle"/>

## 10. Single-Responsibility Principle

The <a href="https://en.wikipedia.org/wiki/Single-responsibility_principle" target="_blank">Single-Responsibility Principle</a> (SRP) states that every module, class or function in a computer program should have responsibility over a single part of that program's functionality, and it should [encapsulate](#encapsulation) that part.

It is related to the principle of <a href="https://en.wikipedia.org/wiki/Separation_of_concerns" target="_blank">Separation of Concerns</a> (SOC), and is one of the five <a href="https://en.wikipedia.org/wiki/SOLID" target="_blank">SOLID</a> principles.

<a id="separate-builder-from-object"/>

### 10.1. Separate Builder from Object

One common application of the SRP is separating the builder of a class from the class itself. Often, we have a situation where we want to instantiate a class `C` from information that was calculated previously (or loaded from a file or a database). According to SRP and SOC, the building functionality of an instance of `C` should be separated from `C` itself.

So this is wrong:

```python
class SomeClass:
    @classmethod
    def build(cls, some_input) -> SomeClass:
        # building an instance of SomeClass from some_input
```

We want a separate class:

```python
class SomeClassBuilder:
    def __init__(self, some_input):
        self.some_input = some_input

    def build(self) -> SomeClass:
        # building logic
        return SomeClass(...)
```

Also, if an instance of SomeClass should never change after it is created, then SomeClass should not have modifier accessors such as:

```python
def set_some_member(self, value):
```

Instead, the constructor of SomeClass should get all the information at once, and this constructor should be used at the end of the build method of the Builder. Therefore, it is convenient to use [attrs](#TBD-link) to define `SomeClass`.

Additionally, if the work of the Builder is based not on information calculated previously, but on information that is loaded from a file or a database, then the loading itself should be done by a separate Loader class:

```python
class LoadSomeClass:
    def __init__(self, resource_location):
        ...
    def load(self) -> SomeData:
        ...
```

The sequence is: Instantiating LoadSomeClass with the location of the data (filepath, DB info, etc.), calling its `load` method to get the loaded data. Then feeding this data into the constructor of `BuildSomeClass`, and calling its `build` method, to get the instance of `SomeClass`.

<a id="more"/>

## 11. More

See also:

- <a href="https://en.wikipedia.org/wiki/SOLID" target="_blank">SOLID</a>
- <a href="https://www.youtube.com/watch?v=RT-npV1JRKE" target="_blank">The SOLID Principles</a>
- Don't optimize prematurely - instead, use a profiler to optimize only the parts that really need it.
