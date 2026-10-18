# Copilot planning rules

Applies to any planning deliverable in this epic: a story proposal, an increment plan, or a design pass.
Referenced by name from each prompt.  Read alongside `doc/developer_docs/copilot_session_rules.md`,
which covers evidence, gates and logging.

## Every plan

**Code style I (the developer) prefer.** Lean object-oriented.  Data that travels together with the
operations on it is a class, not a dict passed between functions; a module of free functions over the
same dict is the class not yet written.
Methods are named for what they do, never for who calls them, and a method whose behaviour forks on an
optional argument is two methods.  Small pure helpers can stay as static methods.
Where a shape is chosen, the plan shows it as signatures with one-line docstrings before any body is written,
because I judge shape by reading signatures, not prose.

**Enumerate rather than summaraize.**  A plan that says "several call sites" has not established anything.
List every match with its file and line, and give the pattern that found it.

**Provenance before anything moves.** For each body you are adding, moving or deleting, state where it
lives today, what it reads, what calls it, and whether that source is still available after the change.
Reasoning forward from a target shape without tracing backward to check the target is reachable is the
single most expensive error made in this epic so far, and it has never once been caught by a gate.

**Every decision names the alternative it rejected, and why.**  A decision recorded without its
alternative reads as arbitrary to the next session, which then reopens it.  Where a decision is handed
to you as already made, say so, and say whether your own findings support it: a decision marked as
given is still a decision and it can still be wrong.

**Quote the contract text before you deviate from it.** Where you report that the contract cannot be written
as it stands, quote the passage verbatim and cite where it appears, then propose the resolution.  A deviation
raised against remembered contract text has twice turned out to be a misread, and a misread recorded as
a deviation tells the next session the contract said something it did not.

**Falsify at most two assertions, chosen for distinct failure signatures.** For every other assertion, state
what reverting it would report and do not apply the revert.  Each falsification is an edit, a suite run,
a restore and a verification, so an uncapped set costs more than the write it is checking.  Where two variants
differ in what they prove, as an absent call differs from a call outside a lock, that pair is the one to spend on.
Run each variant against the module that holds its predicted failures, not the full suites.

**Say which tests break, before you write anything.** Name each test module that will fail and
the reason it will fail.  A claim that a module is unaffected has to rest on a search for
subclasses and construction sites of the class you are changing, across the whole test tree,
not on reading that module's fixtures.

**Name the one assertion that pins the behaviour change.**  If a plan cannot say which assertion
would fail were the change reverted, the change is not yet specified well enough to write.

**And do not write the ones that restate it.** A test whose failure mode is not distinct from another
tests's failure mode is not a second test, and a predicted-names list longer than the behaviour
has distinct ways of being wrong is the signal to cut.
Six tests for one trigger, where the trigger delegates or logs a no-op, is four more than the behaviour has to say.

**Plan the manual check before the write, not after it.**  State what to do in the running application,
what to read, and what result would mean failure.  The gates in this codebase do not cover the
push path to the browser, and three of the most consequential defects found in the previous story
were all found by running the application after every gate passed. 

**Plan the manual check before the write, not after it.** State what to do in the running application,
what to read, and what result would mean failure.  The gates in this codebase do not cover the push
path to the browser, and three of the most consequential defects found in the previous story were all
found by running the application after every gate passed.  Cite the source line that emits the observable
you are asking the reader to read, and name the log level needed to see it, and see where it is written.
Where a check tells the reader to open or edit a file, cite the key or the path as the tree spells it,
not as the check remembers it.  A check resting on a log line that
no code writes cannot fail for the right reason, and its silence reads as a defect in the increment.  Where no
observable exists, say so and propose no check: some criteria close on a gate and a real-scene test, and an
unrunnable check is worse than none. 
And the check belongs to the increment whose subject it tests, not to whichever increment happens to
carry the line of code it exercises.

**Flag anything whose failure would be silent,** meaning the code compiles, the gates pass, and the
behaviour is wrong.  Those are the parts that get the heaviest review and the most careful manual check.

**A new injection point takes no default.** Where a plan adds a constructor parameter, a setter or a sender that something
upstream must supply, say whether a default would let the wiring be omitted with every gate green.  Prefer required, so
the omission is a complete error at the construction site.

**A MagicMock absorbs a new method for calls, not for values.** Where a change hands a new read's return into a model
field, search every test that runs that path, against any renderer or double, adn state per module whether the value
is validated, serialized or asserted downstream.

**A shared double cannot tell two objects apart.**  Where an assertion has to distinguish a write to one object
from a write to another, state what the module's double returns for each; where it returns one object for both, the
pin does not belong in that module and the plan says where it goes instead.

**A correct server object is not evidence about what the client receives.**  State what the client is served, not only
what the server holds.  Server-side state crosses to the browser through a serializable cache, and a live read
establishes nothing about that cache's contents.

**Cite, do not recall.** Every claim about existing code cites the audit or a search you run in this turn.
Do not write from your own summary of an earlier turn in the same session.

**A defect closed incidentally by a wider change is closed only under a stated condition.**  Where you record that your change
probably fixes something outside its scope, name the case in which your change does not run.  Without it the next session
tests the path that works and closes an item that is still live on the other one.

**Carry the unknowns rather than closing them quietly.** Where the evidence said "cannot determine", either
resolve it with a search now or carry it forward as an open item, naming what would settle it
and where it gets settled.

## Proposals additionally

A proposal is the frozen contract.  The increment sessions read it and nothing else, so anything not written
into it does not reach them.

**State the contract in full,** not by reference: the models with every field name and typed, the trigger names
spelled verbatim on both stacks, and the interface signatures.  Where a method has more than one implementation,
state what each one owes, rather than naming the method and leaving the rest implied.

**Break the work into increments that are additive first and subtractive last**, each one leaving the tree
in a state where the gates can still run.  FOr each increment give its intent, its file list including
test modules, the model it should be run with and why, the acceptance criterion it closes if any, and its
ordering constraints against the others.  Say explicitly which increments may share a session and which
must not, and give the reason in each case.

**Map every acceptance criterion to the increment that closes it and to how it is verified**: a gate,
an inspection, or a manual check in the running application.

**Leave a rulings section, empty at first.** Decisions taken during plan review land there, each naming the
increment it binds.  Without it, a ruling made in review reaches nobody, because the reviewer's own
documents are not visible to the sessions doing the work.

## Increment prompts

A prompt is built from the proposal's prompt-template section and filled from its increments section.
These rules govern that fill, so the template does not have to restate them and the person typing the prompt
does not have to supply them.

**Every prompt opens with a STATE line.** Report `git status` and `HEAD`, stop if the tree is not clean, and
state the base commit by hash taken from `git log`, never from an earlier log entry.

**The read-first list is derived, not summarized.** Take the increment's file list, cross it with the symbols
the contract names in those file, and list them anchored by symbol with no line numbers.  Where the increment
changes a class, add subclasses and construction sites of that class across the whole test tree.  "The symbols
this increment touches" is not a list.

**Per-session constraings go in their own block.** The proposal's story-wide list is true in every increment of
the story.  Anything true of one session only goes below it under a separate heading.  Appending to the
story-wide list silently promotes a per-session constraint to a story-wide one, and the next prompt built from
that list inherits it. 

**A combined session states each increment separately.** Give scope, intent, closes and depends-on per increment
rather than merged, and say in which order they are written and gated.  Name the line in the increments section
that permits the grouping.