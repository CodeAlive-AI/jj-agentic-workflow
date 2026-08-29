# Stray files, litter, and captured secrets

Read when a file entered a change that should not be there — scratch output, a build artifact, a
vendored tree, or credentials. Behaviour below was reproduced on jj 0.44.0.

## Why this is a jj-specific hazard

Git has an untracked state that quietly holds a stray file until someone stages it. jj has none:
any non-ignored file joins the current change the first time *any* jj command runs, including the
ones that look like reads. So the window between "the file appeared" and "the file is committed"
is effectively zero, and nobody has to type `add` for it to happen.

Consequences worth planning around:

- Ignore rules must be right **before** an agent starts, not fixed afterwards.
- Test runs, formatters, code generators and lockfile tools change files; snapshot and inspect the
  change after running them, not only before.
- `snapshot.max-new-file-size` (1 MiB default) turns an oversized new file into a hard failure of
  every jj command — and while snapshotting fails, nothing is being recorded at all.

## `.gitignore` is not retroactive

Measured sequence:

| Step | Files in the change |
|---|---|
| `.env` created, any jj command runs | `.env`, `keep.txt` |
| `.env` added to `.gitignore`, then edited | `.env`, `.gitignore`, `keep.txt` — **still tracked, still snapshotting new edits** |
| `jj file untrack .env` | `.gitignore`, `keep.txt` — file remains on disk |

So the order is: ignore the path, then `jj file untrack <path>`. Ignoring alone changes nothing
for a file jj already knows about.

## A captured secret is an exposed credential

Untracking cleans the current change, not the record. After `.env` was deleted and ignored, the
change was clean — and the value was still printable from an earlier entry of that change's own
evolution history:

```bash
jj --ignore-working-copy evolog -r <change> --no-graph -T 'commit.commit_id().short()'
# an earlier entry still yields the file, and its contents, verbatim
```

`jj evolog` is local and never pushed, so this is usually not a publication event — but the
credential has been written into repository storage and is recoverable by anyone with the disk.
The correct response is therefore:

1. Stop and tell the user, naming the file and the change — do not print the value.
2. Untrack the path and fix the ignore rules so it cannot return.
3. Say plainly that removal does not undo exposure, and recommend rotating the credential.
4. Only then discuss purging (abandoning the affected hidden commits, `jj util gc`), which is a
   user decision and does not substitute for rotation.

Never report the deletion as if it resolved the problem. A tidy working copy and an exposed
secret look identical from the outside, which is exactly why the claim has to be explicit.
