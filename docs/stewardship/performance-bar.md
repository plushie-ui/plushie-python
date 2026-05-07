# Performance bar

plushie-python is meant to feel lightweight in use and lightweight
in the process listing. That is a baseline expectation, not an
optimization target chased after the fact.

The runtime sits between every event and every render. Work it
does on a hot path is paid by every interaction in every app.
Idle apps that draw CPU draw battery; runtimes that walk the tree
six times per update are felt on larger trees even when each walk
profiles cleanly. Python's per-call overhead is real (interpreter
dispatch, allocation, the GIL); a runtime that is sloppy about
per-event work is felt sooner here than in a JIT'd or compiled
language. The whole point of going native through a typed wire is
that the host should feel lighter than what it replaces; a runtime
that pegs CPU loses that on its own merits.

## Working principle

Lightweight is achieved by not doing unnecessary work in the first
place. Optimizing a hot path after the fact is sometimes
necessary; far more of the win comes from never letting the work
appear.

Each piece of work has a cost. Individually most of them are
cheap; the cost compounds across a frame, an interaction, an
app's lifetime, the user's battery. A tree walk that runs in
0.3ms looks fine in isolation; six of them per update on a medium
tree is visible latency. Watch the compounding, not just the
individual microbenchmark.

The canonical example: tree normalization threading scope and
window context through a single traversal that produces wire
nodes directly, instead of multiple post-hoc walks for scope
splitting, ID generation, and prop encoding. None of the
alternative walks would have flagged as a hotspot in a profile of
a small app. The consolidation is correct work because the
redundant work is unnecessary, the change makes the code clearer
rather than worse, and the aggregate cost matters for larger
apps and edge cases. That is the shape of performance work that
earns its place without a benchmark.

## Readability is the bound

Optimizations that obscure intent trade a forever cost (every
future reader) against a one-time benefit. Decline that trade by
default.

Worth doing without a benchmark because the win is obvious in
shape and readability is preserved or improved:

- Consolidating redundant traversals, dispatches, or
  serialization passes.
- Picking the right data structure for a known access pattern
  (`dict` lookup over linear scan when N is large; `frozenset`
  over `tuple` for membership checks; `tuple` over `list` for
  immutable collections so identity comparisons are valid).
- Avoiding a clearly unnecessary allocation, copy, or
  comprehension that another function on the same data
  already did.
- Localized refactors where the optimized form is also the
  cleaner form.
- Removing per-frame work that does not depend on per-frame
  inputs (move it to startup, to subscription diff, or to the
  edge where the input changes).

Need a benchmark, profile, or repro before they land, because
the readability cost is real:

- Clever encoding, lookup, or layout schemes that change how
  the code reads.
- Big-O claims of the form "this is O(n) on a hot path"
  without realistic N. Many such claims have N in the dozens,
  where the constant factor of a `dict.get` or list scan is
  worse than the linear walk.
- Optimizations on idle or rarely-hit paths (startup, settings
  parsing, error paths, dev-mode overlays).
- Anything that asks the reader to look up a comment to
  understand what the code is doing.
- C-extension or `cython` reaches where pure Python with a
  better algorithm would do.

Measurement is a tiebreaker for the second list, not a gate on
the first.

## What lightweight looks like

Numeric direction for the realistic application profile (a few
hundred to about a thousand active tree nodes, dozens of images,
one to five fonts):

- **Frame budget.** 16.67ms (60fps) for a single update cycle
  end-to-end (event arrival, app `update`, `view`, tree diff,
  wire emit). Most of that budget belongs to the renderer; the
  SDK side should be a small slice.
- **Event-to-update.** Visible by the next frame.
  Sub-millisecond wire round-trip on a local pipe.
- **Idle CPU.** When nothing is happening, the runtime does no
  measurable work. No periodic polling, no animation tick when
  no animation is active, no spinning subscription threads, no
  per-frame walks when the tree has not changed. Timer threads
  for `Subscription.every` only run while the subscription is
  active.
- **Subscription cost.** Subscribing to a high-frequency source
  is the user's choice; per-subscription `max_rate` lets the
  renderer coalesce events before the wire so the cost is
  bounded by what the user opts into.
- **Resident memory.** A few tens of MiB for an idle small app.
  Memory grows with widget state and tree size, not with
  runtime bookkeeping. Internal caches bound their size.

These are direction, not contracts. There is no benchmark
infrastructure in the repo today; numbers should be tightened
or relaxed when measurement disagrees.

## GIL realism

The runtime thread, the reader thread, the executor pool, and
timer threads all contend for the GIL. Real parallelism comes
from the renderer subprocess (separate process, separate GIL),
not from the SDK side. CPU-bound user work in `Command.task`
does not benefit from the executor in the way I/O-bound work
does; that is a Python language fact and not a plushie design
problem to solve. The runtime aims to keep its own per-event
work small enough that the GIL contention from
infrastructure threads is in the noise.

If a future Python release with no-GIL builds becomes the
deployment shape, the runtime's thread-based design is
positioned to take advantage. Until then, the lightweight bar
is what it is.

## Tree diff is the load-bearing piece

`plushie.tree.diff` is the hot path that runs every cycle the
view tree changes. Worth preserving:

- Single-pass diff with the four-op patch alphabet
  (`replace_node`, `update_props`, `insert_child`,
  `remove_child`). Children are matched by ID, not position;
  reorders emit `replace_node` for the parent. The cost of an
  unnecessary full re-emit on a large tree is far worse than
  the cost of a clean ID match.
- First render and post-reconnect always send full snapshots;
  diffing is for steady-state updates.
- `WidgetDef`-internal state caching so composite widgets do
  not re-render when neither props nor state changed.

Changes to the diff path that look like cleanups but actually
inflate work per node (extra dict lookups, redundant key
stringification, repeated `prop.get` chains where a destructure
would do) get caught here because the compounding is most
visible.
