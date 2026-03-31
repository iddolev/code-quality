# Encountered Phenomena

Guidelines that were not upheld in code produced by LLMs

1. DRY
   - E.g. Instead o fa small helper function once that calculates current time UTC, 
     this was repeated in several modules that needed it,
     even when the request to add a field with UTC time in common data files was one request, 
     not separate requests
   - 