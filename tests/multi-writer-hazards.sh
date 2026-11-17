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
# Exercise this checkout's wrapper, not whatever `jj land` is installed on the machine.
LAND="$(cd "$(dirname "$0")/../bin" && pwd)/jj-land"

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
case "$(recov undo "jj undo")" in
  *"real work"*) ok "jj 0.46 cross-workspace undo protects the co-worker" ;;
  *) bad "cross-workspace undo damaged the co-worker; requires jj >= 0.46" ;;
esac
# jj 0.47 attributes `workspace add` to the caller, so an undo there takes the new workspace's
# initial commit back and leaves it stale (0.46 refused). Skill rule: discard it with finish --remove.
U="$LAB/r1-add-undo"; rm -rf "$U" "$U-c"; mkdir -p "$U"
( cd "$U"; jj git init --colocate; echo base > base.txt; jj describe -m base
  jj new -m next; jj bookmark create main -r @- ) >/dev/null 2>&1
jj -R "$U" workspace add --sparse-patterns full --name c -r main -m "c: task" "$U-c" >/dev/null 2>&1
( cd "$U"; jj undo ) >/dev/null 2>&1
case "$(cd "$U-c" && jj status 2>&1)" in
  *stale*) ok "undo in the caller takes back a new workspace's start (rule is necessary)" ;;
  *) bad "undo in the caller left the new workspace intact — rule may be obsolete, re-check" ;;
esac
for m in "op-restore:jj op restore @OP@"; do
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
OUT=$( cd "$R"; "$LAND" @ 2>&1 ); case "$(desc "$R" main)" in "one") ok "forward land works" ;; *) bad "forward land failed: $OUT" ;; esac
BASE=$(jj -R "$R" --ignore-working-copy log -r 'description(substring:"base")' --no-graph -T commit_id)
OUT=$( cd "$R"; "$LAND" "$BASE" 2>&1 )
case "$OUT" in *REFUSED*|*ancestor*) ok "backwards land refused" ;; *) bad "backwards land NOT refused: $OUT" ;; esac
( cd "$R"; jj new "commit_id(\"$BASE\")" -m "sibling"; echo s > s.txt; jj status ) >/dev/null 2>&1
OUT=$( cd "$R"; "$LAND" @ 2>&1 )
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
( cd "$R"; jj new main -m "one"; echo 1 > one.txt; jj status; "$LAND" @ ) >/dev/null 2>&1
BASE=$(jj -R "$R" --ignore-working-copy log -r 'description(substring:"base")' --no-graph -T commit_id)
( cd "$R"; "$LAND" "$BASE" ) >/dev/null 2>&1
EVLOG="$JJ_AGENT_STATE/events.jsonl"
if [ -s "$EVLOG" ]; then ok "guards write events (silence would be indistinguishable from success)"; else bad "no events written — guards are not instrumented"; fi
grep -q '"event":"land-succeeded"' "$EVLOG" 2>/dev/null && ok "a successful land is recorded" || bad "successful land not recorded"
grep -q '"rule":"sideways-or-backwards-move"' "$EVLOG" 2>/dev/null && ok "a refusal is recorded with its rule name" || bad "refusal rule not recorded"
python3 -c "import json,sys; [json.loads(l) for l in open('$EVLOG')]" 2>/dev/null && ok "event log is valid JSONL" || bad "event log is malformed"
unset JJ_AGENT_STATE

say "8. jj abandon is the back door around the trunk guard"
R=$(mk abandon-bookmark)
( cd "$R"; jj new main -m "landed work"; echo w > w.txt; jj status; "$LAND" @; jj new -m next ) >/dev/null 2>&1
MAIN=$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)
OUT=$( cd "$R"; jj abandon "commit_id(\"$MAIN\")" 2>&1 )
case "$(jj -R "$R" --ignore-working-copy log -r 'bookmarks(exact:"main")' --no-graph -T commit_id 2>/dev/null)" in
  "") ok "abandon DELETED the bookmark it pointed at (rule is necessary)" ;;
  *)  bad "main survived the abandon — re-check the rule: $OUT" ;;
esac
R=$(mk abandon-retain)
( cd "$R"; jj new main -m "landed work"; echo w > w.txt; jj status; "$LAND" @; jj new -m next ) >/dev/null 2>&1
MAIN=$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)
PARENT=$(jj -R "$R" --ignore-working-copy log -r "commit_id(\"$MAIN\")-" --no-graph -T commit_id)
( cd "$R"; jj abandon "commit_id(\"$MAIN\")" --retain-bookmarks ) >/dev/null 2>&1
NOW=$(jj -R "$R" --ignore-working-copy log -r 'bookmarks(exact:"main")' --no-graph -T commit_id 2>/dev/null)
[ "$NOW" = "$PARENT" ] && ok "--retain-bookmarks still moves trunk BACKWARDS (jj land would refuse it)" \
                       || bad "unexpected --retain-bookmarks result: '$NOW'"
OUT=$( cd "$R"; jj config set --repo aliases.abandon '["status"]' 2>&1; jj abandon --help 2>&1 | head -2 )
case "$OUT" in *"Cannot define an alias that overrides"*) ok "abandon cannot be wrapped by an alias (guard must sit in the host)" ;;
  *) bad "an alias now shadows abandon — the wrapper layer may be available: $OUT" ;; esac

GUARD="$(cd "$(dirname "$0")/../hooks" && pwd)/jj-abandon-guard.py"
R=$(mk abandon-guard)
( cd "$R"; jj new main -m "landed work"; echo w > w.txt; jj status; "$LAND" @; jj new -m "my wip"; echo m > m.txt; jj status ) >/dev/null 2>&1
MAIN=$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)
BASE=$(jj -R "$R" --ignore-working-copy log -r 'description(substring:"base")' --no-graph -T commit_id)
guard() { python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","cwd":sys.argv[1],"tool_input":{"command":sys.argv[2]}}))' "$R" "$1" | python3 "$GUARD" >/dev/null 2>&1; echo $?; }
[ "$(guard 'jj abandon @')" = 0 ] && ok "guard allows abandoning your own unlanded change" || bad "guard blocked a legitimate abandon"
[ "$(guard 'jj abandon $old')" = 2 ] && ok "guard refuses a target from a shell substitution" || bad "guard allowed a stale-variable target"
[ "$(guard "jj abandon 'commit_id(\"$MAIN\")'")" = 2 ] && ok "guard refuses abandoning a bookmarked commit" || bad "guard allowed deleting a bookmark"
[ "$(guard "jj abandon 'commit_id(\"$BASE\")'")" = 2 ] && ok "guard refuses abandoning landed history" || bad "guard allowed rewriting landed history"
[ "$(guard 'echo abandon ship')" = 0 ] && ok "guard ignores commands that merely mention abandon" || bad "guard fired on unrelated text"

say "9. a divergent change cannot be landed by accident"
R=$(mk divergent)
( cd "$R"; jj new main -m "work"; echo w > w.txt; jj new -m next2 ) >/dev/null 2>&1
q() { jj -R "$R" --ignore-working-copy log -r "$1" --no-graph -T 'commit_id ++ "\n"' 2>/dev/null; }
X=$(q @-); OP=$(jj -R "$R" --ignore-working-copy op log -n1 --no-graph -T id 2>/dev/null)
# Two writers rewrite the same change from the same operation: one edits the description,
# the other (by accident) empties it — the shape of the empty-twin landing incident.
( cd "$R"; jj --ignore-working-copy --at-op "$OP" describe -r "commit_id(\"$X\")" -m "work, edited"
  jj --ignore-working-copy --at-op "$OP" restore --from main --into "commit_id(\"$X\")"
  jj log ) >/dev/null 2>&1
FULL=$(q 'divergent() & description(substring:"edited")')
EMPTY=$(q 'divergent() & empty() & description(substring:"work") & ~description(substring:"edited")')
CID=$(jj -R "$R" --ignore-working-copy log -r "commit_id(\"$FULL\")" --no-graph -T change_id 2>/dev/null)
MAIN0=$(q main)
[ -n "$FULL" ] && [ -n "$EMPTY" ] && ok "concurrent rewrites left an empty and a non-empty twin" \
                                  || bad "could not build divergent twins: full='$FULL' empty='$EMPTY'"
refused() { # $1 label, $2 revision to land
  local out; out=$( cd "$R"; "$LAND" "$2" 2>&1 )
  if [[ "$out" == *REFUSED* && "$(q main)" == "$MAIN0" ]]; then ok "$1"; else bad "$1: $out"; fi
}
refused "land refuses the empty twin and leaves trunk in place" "commit_id(\"$EMPTY\")"
( cd "$R"; jj new "commit_id(\"$EMPTY\")" -m child; echo c > c.txt; jj status ) >/dev/null 2>&1
refused "land refuses a plain child of a divergent twin" "@"
refused "land refuses a revision that resolves to both twins" "change_id(\"$CID\")"
( cd "$R"; jj new main -m "work, rebuilt"; jj restore --from "commit_id(\"$FULL\")"; "$LAND" @ ) >/dev/null 2>&1
FILES=$( cd "$R"; jj --ignore-working-copy file list -r main 2>/dev/null )  # -R from outside prints cwd-relative paths
[ "$(desc "$R" main)" = "work, rebuilt" ] && [[ $'\n'"$FILES"$'\n' == *$'\nw.txt\n'* ]] \
  && ok "the printed recovery (new + restore --from the full twin) lands the work" \
  || bad "recovery recipe failed: main is '$(desc "$R" main)'"
if jj converge --help >/dev/null 2>&1; then
  ( cd "$R"; jj bookmark create twin -r "commit_id(\"$FULL\")"; jj converge --no-interactive -r "change_id(\"$CID\")" ) >/dev/null 2>&1
  NEW=$(q 'bookmarks(exact:"twin")')
  [ -n "$NEW" ] && [ -z "$(q "commit_id(\"$FULL\")::commit_id(\"$NEW\")")" ] \
    && ok "converge moves a bookmark on a twin sideways (reference rule is necessary)" \
    || bad "converge kept the bookmark on a descendant — re-check the reference rule"
fi

say "10. landing reports what the range adds, and refuses forbidden paths"
R=$(mk additions)
( cd "$R"; jj new main -m "add stuff"; echo x > debug.log; echo e > .env.example; mkdir src; echo s > src/app.py
  jj new -m "drop log"; rm debug.log; jj status ) >/dev/null 2>&1
OUT=$( cd "$R"; "$LAND" @ 2>&1 )
[ "$(desc "$R" main)" = "drop log" ] && ok "warnings do not block landing" || bad "land blocked by a warning: $OUT"
grep -q 'WARN.*debug\.log.*deleted again' <<<"$OUT" && ok "added-then-deleted litter is still reported" || bad "add-then-delete not reported: $OUT"
grep -q 'WARN.*\.env\.example' <<<"$OUT" && bad ".env.example was flagged: $OUT" || ok ".env.example is not flagged"
grep -q 'src/app\.py' <<<"$OUT" && ok "ordinary additions are listed" || bad "src/app.py missing from the report: $OUT"
R=$(mk forbidden)
( cd "$R"; jj config set --repo land.forbidden "'root-glob:\"secrets/**\"'"
  jj new main -m "oops"; mkdir secrets; echo k > secrets/k.txt; jj new -m "remove"; rm -r secrets; jj status ) >/dev/null 2>&1
MAIN0=$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)
OUT=$( cd "$R"; "$LAND" @ 2>&1 )
if [[ "$OUT" == *REFUSED*secrets/k.txt* && "$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)" == "$MAIN0" ]]; then
  ok "a forbidden path refuses the land, even when a later commit deletes it"
else bad "forbidden path not refused: $OUT"; fi

say "11. land.check gates the move and sees the target"
R=$(mk check)
( cd "$R"; jj config set --repo land.check "'test \"\$(cat ../check-verdict)\" = pass && echo \"checked \$1 base=\$JJ_LAND_BASE\"'"
  jj new main -m "checked work"; echo c > c.txt; jj status ) >/dev/null 2>&1
MAIN0=$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)
TARGET=$(jj -R "$R" --ignore-working-copy log -r @ --no-graph -T commit_id)
echo fail > "$LAB/check-verdict"
OUT=$( cd "$R"; "$LAND" @ 2>&1 )
if [[ "$OUT" == *REFUSED*land.check* && "$(jj -R "$R" --ignore-working-copy log -r main --no-graph -T commit_id)" == "$MAIN0" ]]; then
  ok "a failing land.check refuses the land and leaves trunk in place"
else bad "failing land.check did not refuse: $OUT"; fi
echo pass > "$LAB/check-verdict"
OUT=$( cd "$R"; "$LAND" @ 2>&1 )
[[ "$OUT" == *"checked $TARGET base=$MAIN0"* ]] && ok "land.check receives the target id and the base" || bad "land.check arguments wrong: $OUT"
[ "$(desc "$R" main)" = "checked work" ] && ok "a passing land.check lets the land proceed" || bad "passing land.check blocked: $OUT"

say "12. trunk moving during land.check: refused, unless the move stays inside land.recheck-exempt"
# The check itself plays the parallel writer: on its first run it lands the commits
# described in ../move-<name> from a second workspace, then passes. A counter file
# shows whether the check ran again.
mkmove() { # $1 name, $2 exempt fileset or "", $3 file our range writes -> repo path
  local R; R=$(mk "move-$1")
  ( cd "$R"
    mkdir -p docs src; echo shared > docs/shared.md; echo code > src/app.txt
    jj describe -m base2; jj new -m next; jj bookmark set main -r @-
    jj workspace add --name other -r main "$R-other"
    [ -n "$2" ] && jj config set --repo land.recheck-exempt "'$2'"
    jj config set --repo land.check "'echo run >> ../count-$1; if [ -f ../move-$1 ]; then (cd ../$(basename "$R")-other && bash ../move-$1) >/dev/null 2>&1; rm -f ../move-$1; fi; true'"
    jj new main -m "work"; mkdir -p "$(dirname "$3")"; echo ours >> "$3"; jj new -m "after work"; jj status ) >/dev/null 2>&1
  rm -f "$LAB/count-$1"; echo "$R"
}
main_id() { jj -R "$1" --ignore-working-copy log -r main --no-graph -T commit_id; }
checks() { grep -c run "$LAB/count-$1" 2>/dev/null || echo 0; }
export JJ_AGENT_STATE="$LAB/events12"; mkdir -p "$JJ_AGENT_STATE"; EVLOG="$JJ_AGENT_STATE/events.jsonl"

# a) docs-only move, exemption configured: lands without re-running the check.
R=$(mkmove docs 'root-glob:"docs/**" | root-glob:"**/*.md"' src/feature.txt)
cat > "$LAB/move-docs" <<'EOS'
jj new main -m "docs one"; echo d1 > docs/one.md; jj new -m "docs two"; echo d2 > notes.md
jj new -m tail; jj bookmark set main -r @-
EOS
OUT=$( cd "$R"; "$LAND" @- 2>&1 )
if [ "$(desc "$R" main)" = "work" ] && [ "$(desc "$R" 'main-')" = "docs two" ] && [ "$(checks docs)" = 1 ]; then
  ok "a docs-only move during the check: rebased and landed, check ran once"
else bad "docs-only move not landed automatically (checks=$(checks docs)): $OUT"; fi
[[ "$OUT" == *"land.check NOT re-run"*"docs two"* ]] && ok "the skip is printed with the commits it accepted" || bad "skip not reported: $OUT"
grep -q '"rule":"recheck-skipped"' "$EVLOG" 2>/dev/null && ok "the skip is recorded as rule=recheck-skipped" || bad "skip not recorded in the event log"
[ -z "$(jj -R "$R" --ignore-working-copy diff --from main- --to main --name-only -- '~root-glob:"src/**"')" ] \
  && [ -n "$(jj -R "$R" --ignore-working-copy file list -r main -- 'root:"docs/one.md"')" ] \
  && ok "the landed commit carries only its own change, on top of the docs" || bad "landed tree is wrong"
[ "$(desc "$R" "@-")" = "work" ] && [ -z "$(jj -R "$R" --ignore-working-copy log -r '@ & ~(main::)' --no-graph -T commit_id)" ] \
  && ok "the working copy above the range followed the rebase" || bad "working copy left behind the rebase"

# b) a move that touches a path outside the fileset: today's refusal, nothing rewritten.
R=$(mkmove code 'root-glob:"docs/**"' docs/mine.md)
printf '%s\n' 'jj new main -m "code"; echo c >> src/app.txt; jj new -m tail; jj bookmark set main -r @-' > "$LAB/move-code"
WORK0=$(jj -R "$R" --ignore-working-copy log -r @- --no-graph -T commit_id)
OUT=$( cd "$R"; "$LAND" @- 2>&1 )
if [[ "$OUT" == *REFUSED*"moved while land.check ran"*"src/app.txt"* ]] && [ "$(desc "$R" main)" = "code" ] \
   && [ "$(jj -R "$R" --ignore-working-copy log -r @- --no-graph -T commit_id)" = "$WORK0" ]; then
  ok "a move touching a non-exempt path refuses and rewrites nothing"
else bad "non-exempt move not refused: $OUT"; fi
grep -q '"reason":"non-exempt-path"' "$EVLOG" 2>/dev/null && ok "the refusal reason is recorded" || bad "refusal reason missing"

# c) a docs-only move that would collide with the range: refused before any rebase.
R=$(mkmove clash 'root-glob:"docs/**"' docs/shared.md)
printf '%s\n' 'jj new main -m "docs edit"; echo theirs >> docs/shared.md; jj new -m tail; jj bookmark set main -r @-' > "$LAB/move-clash"
WORK0=$(jj -R "$R" --ignore-working-copy log -r @- --no-graph -T commit_id)
OUT=$( cd "$R"; "$LAND" @- 2>&1 )
if [[ "$OUT" == *REFUSED*"docs/shared.md"* ]] && [ "$(desc "$R" main)" = "docs edit" ] \
   && [ "$(jj -R "$R" --ignore-working-copy log -r @- --no-graph -T commit_id)" = "$WORK0" ] \
   && [ -z "$(jj -R "$R" --ignore-working-copy log -r 'conflicts()' --no-graph -T commit_id)" ]; then
  ok "a move that could conflict with the range refuses and rewrites nothing"
else bad "conflicting move not refused cleanly: $OUT"; fi

# d) no land.recheck-exempt: today's refusal even for a docs-only move.
R=$(mkmove none '' src/feature.txt)
printf '%s\n' 'jj new main -m "docs only"; echo d > docs/one.md; jj new -m tail; jj bookmark set main -r @-' > "$LAB/move-none"
OUT=$( cd "$R"; "$LAND" @- 2>&1 )
if [[ "$OUT" == *REFUSED*"moved while land.check ran"*"not set"* ]] && [ "$(desc "$R" main)" = "docs only" ]; then
  ok "without land.recheck-exempt a moved trunk still refuses"
else bad "no-config move not refused: $OUT"; fi

# e) a rename out of a protected path into the fileset is not docs-only.
R=$(mkmove rename 'root-glob:"docs/**"' src/feature.txt)
printf '%s\n' 'jj new main -m "move code to docs"; mv src/app.txt docs/app.txt; jj new -m tail; jj bookmark set main -r @-' > "$LAB/move-rename"
OUT=$( cd "$R"; "$LAND" @- 2>&1 )
[[ "$OUT" == *REFUSED*"src/app.txt"* ]] && ok "a rename out of a protected path refuses" || bad "rename out of a protected path accepted: $OUT"
unset JJ_AGENT_STATE

printf '\n\033[1mtotal: %d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
