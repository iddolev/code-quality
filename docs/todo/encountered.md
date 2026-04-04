# Encountered Phenomena

Guidelines that were not upheld in code produced by LLMs

1. DRY
   - E.g. Instead of a small helper function once that calculates current time UTC, 
     this was repeated in several modules that needed it,
     even when the request to add a field with UTC time in common data files was one request, 
     not separate requests
2. ~~The body of a function may not exceed 20 lines~~
3. ~~If the body of a function exceeds 10 lines, 
   usually the function should be re-written to include the high-level algorithm for the function,
   which calls smaller helper functions, to make the function readable.~~
4. ~~Nesting~~
5. Error printing - should be to stderr or a log, not to stdout
6. regex
   - sometimes string instead of compiling
   - sometimes re.compile done inside a function instead of once at module level
7. naming variables with one letter or too short (e.g. itype instead of issue_type)