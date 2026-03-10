Read all markdown files under the `instructions/` folder. These contain code quality guidelines.

Then, for each Python file under the `scripts/` folder, review it against all the guidelines from the instruction files. 
For each guideline violation found, fix the code to comply with the guideline,
but do so very cautiously, without changing the code's operation and meaning,
and if you are in doubt, ask the user whether to do this change. 
After fixing, show a summary of what was changed and which guidelines were applied.