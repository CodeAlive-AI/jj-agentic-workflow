# Clean local history

Inspect `jj status`, `jj diff --git`, and the mutable stack before rewriting it.

- Prefer `jj absorb --from @ --into <mutable-ancestor-revset>` when edits clearly belong in
  existing local ancestors. Review the result with `jj op show -p`, then run `jj status`.
- Use `jj squash --from <source> --into <destination> -m "<description>"` only with explicit
  revisions. Run `jj status` afterward.
- Squashing merges diffs but discards source descriptions. Before folding, read every
  description being absorbed (`jj log -r <sources> --no-graph -T 'description ++ "\n---\n"'`)
  and write the destination a fresh description for the combined diff: keep decisions that
  still hold (constraints, rejected alternatives), drop what the fold itself cancelled, drop
  WIP noise. Unsure whether a decision still holds — or folding changes you did not author —
  carry the text verbatim instead of paraphrasing: an extra paragraph is free, a lost
  constraint is an incident. `--use-destination-message` is for genuinely empty or
  placeholder source descriptions only.
- Do not use interactive `jj split`, `-i`, or `--tool`. When whole paths divide cleanly, use
  `jj split -r <change> -m "<description>" <filesets...>`; otherwise create explicit changes and
  move the files manually.
- Rewrite only mutable local work. Never rewrite a pushed change without explicit authorization.
