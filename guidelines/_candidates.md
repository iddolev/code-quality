# Candidate Guidelines & Not Sure If I Want

<a id="use-blank-lines-to-separate-logical-steps"/>

## Use Blank Lines to Separate Logical Steps

If a function has more than 8 lines, you may exercise judgment to decide 
whether to add blank lines in order to group related statements into visual "paragraphs."
Each group should have at least 2 lines and should represent one logical step of the function's algorithm.
This makes the function's structure scannable at a glance,
even when it is short enough that extracting helper functions would be overkill.

For example, instead of:

```python
def create_report(records: list[Record], output_path: Path) -> None:
    valid = [r for r in records if r.is_active]
    intermediate = compute_intermediate(valid)
    totals = compute_totals(intermediate)
    header = format_header(totals)
    rows = [format_row(r) for r in valid]
    text = header + "\n" + "\n".join(rows)
    text += f"\nTotals:{totals}"
    output_path.write_text(text, encoding="utf-8")
    logger.info("Report written to %s", output_path)
```

you may (but you don't have to) use the following, 
if your judgment says it makes the code more readable:

```python
def create_report(records: list[Record], output_path: Path) -> None:
    valid = [r for r in records if r.is_active]
    intermediate = compute_intermediate(valid)
    totals = compute_totals(intermediate)

    header = format_header(totals)
    rows = [format_row(r) for r in valid]
    text = header + "\n" + "\n".join(rows)
    text += f"\nTotals:{totals}"

    output_path.write_text(text, encoding="utf-8")
    logger.info("Report written to %s", output_path)
```

The three visual groups — filter/aggregate, format, write — let the reader
grasp the function's flow without reading every line.
