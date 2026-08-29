#!/usr/bin/env bash
# Regression suite for the multi-agent jj guards (global config + jj land + skill rules).
# Run: bash tests/multi-writer-hazards.sh   (uses a throwaway temp repo set; JJ_LAB_DIR overrides)
set -uo pipefail
LAB="${JJ_LAB_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/jj-hazards.XXXXXX")}"
PASS=0; FAIL=0
ok()  { printf '  \033[32mPASS\033[0m  %s\n' "$*"; PASS=$((PASS+1)); }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAIL=$((FAIL+1)); }
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

mk() { # $1 name -> path with base/main
  local d="$LAB/r-$1"; rm -rf "$d"; mkdir -p "$d"
  ( cd "$d"; jj git init --colocate; echo base > base.txt
    jj describe -m base; jj new -m next
    jj bookmark create main -r @- ) >/dev/null 2>&1
  echo "$d"
}
desc() { jj -R "$1" --ignore-working-copy log -r "$2" --no-graph -T 'description.first_line()' 2>/dev/null; }

say "1. recovery mode: forward fixes spare the co-worker, rewinds do not"
recov() { # $1 label, $2 command
  local d="$LAB/r1-$1"; rm -rf "$d" "$d-b"; mkdir -p "$d"
  ( cd "$d"; jj git init --colocate; echo base > base.txt; jj describe -m base
    jj new -m next; jj bookmark create main -r @- ) >/dev/null 2>&1
  jj -R "$d" workspace add --name b -r main -m "b: task" "$d-b" >/dev/null 2>&1
  ( cd "$d"; echo junk > a.txt; jj describe -m "a: oops" ) >/dev/null 2>&1
  local op; op=$(jj -R "$d" --ignore-working-copy op log --no-graph -T 'id ++ "\n"' | sed -n 2p)
  ( cd "$d-b"; echo w > b.txt; jj describe -m "b: real work" ) >/dev/null 2>&1
  ( cd "$d"; eval "${2//@OP@/$op}" ) >/dev/null 2>&1
  desc "$d-b" @
}
for m in "undo:jj undo" "op-restore:jj op restore @OP@"; do
  case "$(recov "${m%%:*}" "${m#*:}")" in
    *"real work"*) bad "${m%%:*} left the co-worker intact — rule may be obsolete, re-check" ;;
    *) ok "${m%%:*} damages a co-worker (rule is necessary)" ;;
  esac
done
for m in "abandon:jj abandon @ --retain-bookmarks" "describe:jj describe -m 'a: corrected'"; do
  case "$(recov "${m%%:*}" "${m#*:}")" in
    *"real work"*) ok "forward ${m%%:*} leaves the co-worker intact" ;;
    *) bad "forward ${m%%:*} damaged the co-worker" ;;
  esac
done

say "2. reads: bare commands snapshot, --ignore-working-copy does not"
R=$(mk reads); ( cd "$R"; jj describe -m "task" ) >/dev/null 2>&1
( cd "$R"; echo stray > stray.txt; jj --ignore-working-copy log -r @ ) >/dev/null 2>&1
F=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T 'diff.files().map(|f| f.path()).join(",")')
case "$F" in *stray*) bad "--ignore-working-copy snapshotted stray.txt" ;; *) ok "--ignore-working-copy left the change alone" ;; esac
( cd "$R"; jj status ) >/dev/null 2>&1
F=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T 'diff.files().map(|f| f.path()).join(",")')
case "$F" in *stray*) ok "bare jj status did absorb stray.txt (rule is necessary)" ;; *) bad "unexpected: status did not snapshot" ;; esac

say "3. global git.abandon-unreachable-commits keeps content when a Git ref vanishes"
[ "$(jj -R "$(mk cfg)" config get git.abandon-unreachable-commits)" = "false" ] \
  && ok "global setting is false" || bad "global setting is not false"
R=$(mk abandon)
( cd "$R"; jj new main -m "feature"; echo work > work.txt; jj bookmark create feature -r @
  jj new -m "follow-up"; echo more > more.txt; jj status; jj git export ) >/dev/null 2>&1
( cd "$R"; git update-ref -d refs/heads/feature; jj status ) >/dev/null 2>&1
TIP=$(jj -R "$R" --ignore-working-copy log -r 'heads(all() & ~empty())' --no-graph -T 'commit_id ++ "\n"' | head -1)
FILES=$(jj -R "$R" --ignore-working-copy file list -r "commit_id(\"$TIP\")" 2>/dev/null | tr '\n' ' ')
case "$FILES" in *work.txt*) ok "work.txt survived the ref deletion" ;; *) bad "work.txt lost: '$FILES'" ;; esac

say "4. git.private-commits refuses to publish unfinished work"
rm -rf "$LAB/r-remote"; git init --bare -q "$LAB/r-remote"
R=$(mk private); ( cd "$R"; jj git remote add origin "$LAB/r-remote"
  jj new main -m "feat: shippable"; echo a > a.txt
  jj new -m "wip: scratch"; echo b > b.txt; jj bookmark set main -r @; jj status ) >/dev/null 2>&1
OUT=$( cd "$R"; jj git push --remote origin --bookmark 'exact:main' 2>&1 )
case "$OUT" in *private*) ok "push of a wip: tip refused" ;; *) bad "wip: tip was publishable" ;; esac
FEAT=$(jj -R "$R" --ignore-working-copy log -r 'description(glob:"feat:*")' --no-graph -T commit_id)
( cd "$R"; jj bookmark set main -r "commit_id(\"$FEAT\")" --allow-backwards ) >/dev/null 2>&1
OUT=$( cd "$R"; jj git push --remote origin --bookmark 'exact:main' 2>&1 )
case "$OUT" in *private*) bad "clean commit wrongly blocked" ;; *) ok "clean commit publishes normally" ;; esac

say "5. jj land guards still hold under the new configuration"
R=$(mk land)
( cd "$R"; jj new main -m "one"; echo 1 > one.txt; jj status ) >/dev/null 2>&1
OUT=$( cd "$R"; jj land @ 2>&1 ); case "$(desc "$R" main)" in "one") ok "forward land works" ;; *) bad "forward land failed: $OUT" ;; esac
BASE=$(jj -R "$R" --ignore-working-copy log -r 'description(substring:"base")' --no-graph -T commit_id)
OUT=$( cd "$R"; jj land "$BASE" 2>&1 )
case "$OUT" in *REFUSED*|*ancestor*) ok "backwards land refused" ;; *) bad "backwards land NOT refused: $OUT" ;; esac
( cd "$R"; jj new "commit_id(\"$BASE\")" -m "sibling"; echo s > s.txt; jj status ) >/dev/null 2>&1
OUT=$( cd "$R"; jj land @ 2>&1 )
case "$OUT" in *rebase*) ok "sideways land refused with a rebase hint" ;; *) bad "sideways land not refused: $OUT" ;; esac
case "$OUT" in *"roots(::"*) ok "hint uses whole-ancestry roots(::...)" ;; *) bad "hint would split a stack: $OUT" ;; esac

say "6. stray files and captured secrets"
R=$(mk stray); T='diff.files().map(|f| f.path()).join(",")'
( cd "$R"; jj describe -m "task"; echo "TOKEN=zzz" > .env; jj status ) >/dev/null 2>&1
F=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T "$T")
case "$F" in *.env*) ok "a new secret file is auto-tracked (no untracked state)" ;; *) bad "unexpected: .env not tracked" ;; esac
( cd "$R"; echo ".env" > .gitignore; echo "TOKEN=zzz2" > .env; jj status ) >/dev/null 2>&1
F=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T "$T")
case "$F" in *.env*) ok ".gitignore alone does NOT untrack it (rule is necessary)" ;; *) bad ".gitignore untracked it — re-check the rule" ;; esac
( cd "$R"; jj file untrack .env ) >/dev/null 2>&1
F=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T "$T")
case "$F" in *.env*) bad "jj file untrack did not remove it" ;; *) ok "jj file untrack removes it from the change" ;; esac
[ -f "$R/.env" ] && ok "untrack left the file on disk" || bad "untrack deleted the file"
LEAK=no
for c in $(jj -R "$R" --ignore-working-copy evolog -r @ --no-graph -T 'commit.commit_id().short() ++ "\n"' 2>/dev/null); do
  jj -R "$R" --ignore-working-copy file show -r "commit_id(\"$c\")" 'root:.env' >/dev/null 2>&1 && LEAK=yes
done
[ "$LEAK" = yes ] && ok "secret still reachable via evolog (rotation rule is necessary)" || bad "evolog no longer holds it — re-check the rule"

say "7. guardrail events are actually recorded"
export JJ_AGENT_STATE="$LAB/events"; mkdir -p "$JJ_AGENT_STATE"
R=$(mk events)
( cd "$R"; jj new main -m "one"; echo 1 > one.txt; jj status; jj land @ ) >/dev/null 2>&1
BASE=$(jj -R "$R" --ignore-working-copy log -r 'description(substring:"base")' --no-graph -T commit_id)
( cd "$R"; jj land "$BASE" ) >/dev/null 2>&1
EVLOG="$JJ_AGENT_STATE/events.jsonl"
if [ -s "$EVLOG" ]; then ok "guards write events (silence would be indistinguishable from success)"; else bad "no events written — guards are not instrumented"; fi
grep -q '"event":"land-succeeded"' "$EVLOG" 2>/dev/null && ok "a successful land is recorded" || bad "successful land not recorded"
grep -q '"rule":"sideways-or-backwards-move"' "$EVLOG" 2>/dev/null && ok "a refusal is recorded with its rule name" || bad "refusal rule not recorded"
python3 -c "import json,sys; [json.loads(l) for l in open('$EVLOG')]" 2>/dev/null && ok "event log is valid JSONL" || bad "event log is malformed"
unset JJ_AGENT_STATE

printf '\n\033[1mtotal: %d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
