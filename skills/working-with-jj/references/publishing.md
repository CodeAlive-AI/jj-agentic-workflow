# Publish through a Git remote

Proceed only with explicit authorization. Use the repository's canonical checkout and its
required publish gate; pure-jj secondary workspaces may not contain Git-dependent tooling.

```bash
jj git fetch --remote origin
jj status
jj log -r 'conflicts()'
jj bookmark list <bookmark> --all-remotes
```

If an existing remote bookmark is not tracked, run `jj bookmark track <bookmark>@origin`. Move
the local bookmark explicitly with `jj bookmark set <bookmark> -r <tip>`, then run `jj status`.

`jj git push` does not execute Git hooks (including `core.hooksPath`). If the repository gates
pushes with a pre-push hook, run it manually first.

If the remote requires verified signatures: jj stamps the committer from the current user
identity on every rewrite (including `jj sign`), and the host verifies the signature against
the committer's account-registered email. Signing with an unregistered identity yields
"unverified" and a rejected push — re-sign with a registered identity
(`JJ_USER=… JJ_EMAIL=… jj sign -r <revset>`) before pushing. Note that jj's default
`signing.behavior = "drop"` removes signatures on rewrite, so sign as the final step. After the repository's publish checks pass:

```bash
jj git push --bookmark <bookmark> --remote origin
jj status
```

Verify that the local and remote bookmarks resolve to the same commit. Never push a conflicted
stack or use raw `git push`.
