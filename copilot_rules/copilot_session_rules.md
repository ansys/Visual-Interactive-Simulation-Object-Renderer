# Copilot session rules

Applies to every session in this epic.  Referenced by name from each prompt.

**Session start**
S1. The proposal and the prompt are the only design sources.  Do not read the increment log; what a prompt needs
    from earlier increments is in its INHERITED block.
S2. Take the base commit from git log, never from a log entry.  Clean means no tracked modifications.  Untracked scratch
    directories are the developer's: they do not make the tree unclean and are never touched.  Stop on any tracked
    modification.

**Evidence**
1. Report pattern text with every search and every match, not counts.
2. A search returning exactly its result cap is not a result.  `grep_search` caps at 20; a 20-result return is a cap hit.
   Re-run it scoped, or per symbol with uncapped `git grep`, and say which you did.
2a. A negative recursive result from the repo root is nto a result either.  `grep_search` and `Get-ChildItem -Recurse` 
   have each returned nothing for file and text that exist.  Re-run with `Select-String` or a directed listing of the
   specific directory.
2b. Every search is single-pattern, literal, pipeline form.  A `Select-String -Pattern` whose text contains a pipe
   returns nothing: the pipe is consumed as a shell pipe before PowerShell sees it, with no error.
   `Select-String -Path <array>` is separately unreliable and has returned nothing where `Get-ChildItem | Select-String`
   found matches. An alternative is therefore not a falsifying search; split it and run each pattern.  A pipe in your 
   pattern is not always an alternation: a Python union type is written with one, so the declaration text you are
   trying to match may carry it.  Search a pipe-free substring either way.
2c. `client_bundle/` is build output, not code.  It is never searched, never read, and never appears in a match table.
   Its contents are stale
   compiled copies of client symbols and a hit there is not a finding.
3. Anchor by symbol.  Every line number you are given is stale.  Every line number you are given is stale. 
   Where the symbol is duplicated, anchoring by symbol is unavailable and the anchor is a neighbour relation:
   identify the line by what precedes and follows it, and verify the edit by the same relation.
3. Anchor by symbol.  Every line number you are given is stale.
4. "Cannot determine" is a correct answer.  Do not give a plausible one instead.
5. Mark each claim read-from-source or inferred.
6. A ruling resting on a list needs a search that could return something outside the list.  Run it.

**Known traps**
T1. `VtkScene.getInstanceAsync` ends with `Object.freeze(instance)`.  New mutable state on `VtkScene` must be a
`#private` field.  A public field assigned after construction throws in the browser and in no gate.
T2. The repository is not Prettier-clean at HEAD.  Format only lines you create; never reformat an existing file.
T3. The mouse buttons are remapped on the way to VTK: a middle press is dispatched as button 0, left and right together
as button 1, right alone as button 2.  A middle drag rotates; pan is the chord.
T4. THe npm and npx PowerShell shims are blocked by the execution policy; call npm.cmd and npx.cmd.  Run pytest as
  .venv\Scripts\python.exe -m pytest; the python on PATH cannot import ansys.visor.  Jest's --testPathPattern is now
  --testPathPatterns.

**Writing code**
7. Plan first, no code in the same turn.  Wait for approval.
7a. Write the approved plan in one turn.  Do not re-read a file already read in this session, except the rule-8
   re-read before the gate.
7b. Never call the ask_user tool.  Every question goes in the response text as a proposed ruling, with its
   recommendation and the alternative it rejects, and the turn ends there.  A stop condition is reported the same way.
7c. End every plan-first response wtih "Rulings needed": a numbered list continuing the plan's numbering. 
    Each item is a title, one or two lines of context, "Recommended:" and "Rejected:" with a one-line reason each.
    Nothing that needs a ruling appears only in the body.
8. Full re-read of every touched file before the gate.  Edits here silently fail to persist; cross-check with
`grep_search`, since `read_file` has reported edits that were not applied.  
8a. The editing tools destroy files, and `insert_edit_into_file` is not a safe fallback.  Both it and
   `replace_string_in_file` have replaced a 478-line source file with the replacement fragment alone, reporting
   success.  Use the normal editing tool, then the rule-8 re-read, which is what catches this.  On damage,
   recover with `git checkout -- <file>`, verify against HEAD with `git diff --stat`, and re-apply that file's edits
   with a scripted exact-string patch: anchor asserted to occur exactly once, line-ending aware (this tree is CRLF),
   writing nothing on a miss.  The script is the recovery path, not the default: writing one per edit costs several
   turns per file and is not warranted by one occurence.
9. Never commit.
9a. A tracked modifictaion you did not make is reported, never reverted.  `git checkout --` is the recovery path for a
   file this session damaged (rule 8a); on any other file it can discard the developer's uncommitted work.
10. No test may compute its expected vaule the way the code under test does.  Expected values are hand-written
literals, and no assertion rests on a VTK-constructed default.
10a. A falsification variant that produces an unpredicted signature is evidence about the variant before it is evidence
about the tests.  Diagnose the variant.  Where a further variant would settle it and the count is capped, mark the
conclusion inference rather than measurement.
10b. Where one call writes both a store and a rendered object, the store write and the object state are separate test
functions.  Lock depth, where a lock is involved, is a third.
10c. A pinned production constant stays a test-side literal.  Importing it makes the test recompute what it exists to pin.
10d.  A falsification variant has to land where the tests can reach.  A variant applied to a class the suite cannot
construct cannot fail, and the green run reads as a pass.
10e.  Docstrings and code comments describe the code, never the process that produced it.  No increment numbers, story
numbers, epic phases, ruling or CC identifiers, proposal section references, or dats.  "Resolves the effective range
for a part's color variable" is a docstring; "Added in 3.5.1 increment 2 per RS-3" is a log entry, and the log fragment
is where it goes.


**Gates**
```
pytest tests/unit ; pytest tests/integration
npx tsc -p tsconfig.app.json --noEmit ; npx tsc -b --force ; npm test ; npm run lint
```
Predict the test-count delta before running.  Reconcile by test function name, not by total.
Before any client edit, capture the jest baseline from src/ansys/visor/visor-client with
`npm test -- --json --outputFile=<a path outside the repo>` and reconcile by full test name, as for pytest.
Plain `tsc --noEmit` is vacuous here and always passes.

**Log**
11. Every preflight finding with its search, every ruling, every deviation, every found-not-fixed item, and the gate
reconciliation.  Diffstate from `git diff --stat`.  A manual check is written as procedure with pass and fail
conditions and a blank result line marked "not run in session".  You do not run it and do not record a result.
Recover exact literals from the tree rather than writing remembered ones.

11a. Write the entry as a new file.  Never append to an existing record through a shell: a here-string append has stripped
every blank line from a file, and the repair double-encoded lines it had not touched, with neither failure visible in the
issuing command's own output.  If you ever do append, verify with `git diff --numstat` and treat any change outside the
appended region as damage.

**Stopping**
12.  If you cannot write something under the frozen contract, stop and report.  That is evidence about the contract,
not about the increment.
