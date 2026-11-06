// Focused research fixtures, not an installed workflow or a performance benchmark.
// node verify.ts /absolute/path/to/jj-0.47.1 /absolute/output-directory
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { isAbsolute, join } from 'node:path';

const [binary, output] = process.argv.slice(2);
assert(binary && output && isAbsolute(binary) && isAbsolute(output), 'Provide absolute binary and output paths');
const lab = mkdtempSync(join(tmpdir(), 'jj047-evidence-'));
const repo = join(lab, 'repo');
mkdirSync(repo);
mkdirSync(output, { recursive: true });
const config = join(lab, 'fixture.toml');
// A synthetic identity in a disposable store; no user config or signing keys are read.
writeFileSync(config, 'user.name="JJ research fixture"\nuser.email="fixture@example.invalid"\nsigning.behavior="drop"\nui.paginate="never"\n');
const env = { ...process.env, JJ_CONFIG: config };
const commands: object[] = [];
const checks: { name: string; evidence: unknown }[] = [];
function jj(args: string[], allowFailure = false, cwd = repo) {
  const r = spawnSync(binary, ['--no-pager', '--color=never', ...args], { cwd, env, encoding: 'utf8' });
  const result = { status: r.status, stdout: r.stdout, stderr: r.stderr };
  commands.push({ args, cwd, ...result });
  writeFileSync(join(lab, 'commands.json'), JSON.stringify(commands, null, 2) + '\n');
  if (r.error || (!allowFailure && r.status !== 0)) throw new Error(JSON.stringify(commands.at(-1)));
  return result;
}
function op() { return jj(['--ignore-working-copy', '--at-op=@', 'op', 'log', '-n', '1', '-G', '-T', 'id']).stdout.trim(); }
function id() { return jj(['log', '-r', '@', '-G', '-T', 'commit_id']).stdout.trim(); }
function log(template: string, revision = '@', operation = '@') {
  return jj(['--ignore-working-copy', '--at-op=' + operation, 'log', '-r', revision, '-G', '-T', template]);
}
const version = jj(['--version']).stdout.trim();
assert(version.startsWith('jj 0.47.1'), 'These fixtures qualify 0.47.1 specifically');
function record(name: string, evidence: unknown) {
  checks.push({ name, evidence });
  writeFileSync(join(output, 'results.json'), JSON.stringify({ version, lab, passed: checks.length, checks }, null, 2) + '\n');
}
const summary = 'json({"conflicts" => revset("mutable() & conflicts()").len(), "divergent" => revset("mutable() & divergent()").len()}) ++ "\\n"';
// TreeValue is not serializable itself; encode selected fields. Missing terms remain null.
const value = 'if(v, json({"object_id" => v.object_id(), "file_type" => v.file_type(), "executable" => v.executable()}), "null")';
const conflictTemplate = `"[" ++ conflicted_files.map(|e| "{\\"path\\":" ++ json(e.path()) ++ ",\\"sides\\":" ++ json(e.conflict_side_count()) ++ ",\\"removes\\":[" ++ e.removed_values().map(|v| ${value}).join(",") ++ "],\\"adds\\":[" ++ e.added_values().map(|v| ${value}).join(",") ++ "]}").join(",") ++ "]\\n"`;
writeFileSync(join(output, 'summary.template'), summary + '\n');
writeFileSync(join(output, 'conflicts.template'), conflictTemplate + '\n');
jj(['git', 'init', '--colocate', '.']);
writeFileSync(join(repo, 'drawing.txt'), 'base\n');
writeFileSync(join(repo, 'second.txt'), 'base\n');
jj(['describe', '-m', 'Fixture base']);
const base = id();
jj(['bookmark', 'create', 'baseline', '-r', base]);
const sides: string[] = [];
for (const side of ['A', 'B', 'C']) {
  jj(['new', base, '-m', 'Fixture side ' + side]);
  writeFileSync(join(repo, 'drawing.txt'), side + '\n');
  writeFileSync(join(repo, 'second.txt'), side + '\n');
  jj(['describe', '-m', 'Fixture side ' + side]);
  sides.push(id());
}
jj(['new', ...sides, '-m', 'Fixture three-side merge']);
const merge = id();
const overview = JSON.parse(log(summary).stdout);
const conflicts = JSON.parse(log(conflictTemplate).stdout);
assert.equal(overview.conflicts, 1);
assert.equal(conflicts.length, 2);
assert.equal(conflicts[0].sides, 3);
assert.equal(conflicts[0].adds.length, 3);
assert.equal(conflicts[0].removes.length, 2);
record('three-side conflict terms and commit-versus-file counts', { overview, conflicts });
const blob = spawnSync('git', ['cat-file', 'blob', conflicts[0].adds[0].object_id], { cwd: repo, env, encoding: 'utf8' });
assert.equal(blob.status, 0);
assert.equal(blob.stdout, 'A\n');
record('Git-backed file object retrieval', { objectId: conflicts[0].adds[0].object_id, content: blob.stdout });
const unsupported = jj(['--ignore-working-copy', '--at-op=@', 'op', 'log', '-n', '1', '-G', '-T', 'json({"operation_id" => id, "commits" => revset("@").map(|c| c.commit_id())})'], true);
assert.notEqual(unsupported.status, 0);
assert.match(unsupported.stderr, /Function `revset` doesn't exist/);
record('revset unavailable in operation templates', unsupported);
const inlineError = log('json({"id" => revset("none()").first().commit_id()})');
assert.equal(inlineError.status, 0);
assert.throws(() => JSON.parse(inlineError.stdout));
record('zero exit status is not proof of valid JSON', inlineError);
const pinned = op();
writeFileSync(join(repo, 'unsaved.txt'), 'Unsnapshotted fixture data\n');
assert.deepEqual(JSON.parse(log(summary).stdout), overview);
assert.equal(op(), pinned);
assert.equal(jj(['--ignore-working-copy', '--at-op=@', 'file', 'list', 'unsaved.txt']).stdout, '');
record('observation neither snapshots disk edits nor creates an operation', { operation: pinned });
unlinkSync(join(repo, 'unsaved.txt'));
jj(['new', base, '-m', 'Independent clean task']);
const global = JSON.parse(log(summary).stdout);
const scoped = JSON.parse(log('json({"conflicts" => revset("(baseline.." ++ commit_id ++ ") & conflicts()").len()})').stdout);
assert.equal(global.conflicts, 1);
assert.equal(scoped.conflicts, 0);
assert.equal(log('commit_id', '@', pinned).stdout, merge);
record('task scope excludes unrelated conflicts; pinned operation preserves prior view', { global, scoped, pinned, pinnedCommit: merge });
jj(['new', base, '-m', 'Fixture deletion']);
unlinkSync(join(repo, 'drawing.txt'));
jj(['describe', '-m', 'Fixture deletion']);
const deletion = id();
jj(['new', deletion, sides[0], '-m', 'Fixture delete versus modify']);
const deleteModify = JSON.parse(log(conflictTemplate).stdout);
assert(deleteModify[0].adds.includes(null));
record('absent conflict term survives as JSON null', deleteModify);
jj(['new', base, '-m', 'Fixture two-hunk base']);
const context = Array.from({ length: 30 }, (_, i) => `unchanged ${i}\n`).join('');
writeFileSync(join(repo, 'drawing.txt'), 'base-start\n' + context + 'base-end\n');
jj(['describe', '-m', 'Fixture two-hunk base']);
const hunkBase = id();
const hunkSides: string[] = [];
for (const side of ['X', 'Y', 'Z']) {
  jj(['new', hunkBase, '-m', 'Fixture two-hunk ' + side]);
  writeFileSync(join(repo, 'drawing.txt'), side + '-start\n' + context + side + '-end\n');
  jj(['describe', '-m', 'Fixture two-hunk ' + side]);
  hunkSides.push(id());
}
jj(['new', ...hunkSides, '-m', 'Fixture two-hunk merge']);
assert.equal((readFileSync(join(repo, 'drawing.txt'), 'utf8').match(/^<<<<<<< /gm) || []).length, 2);
const editor = join(lab, 'resolve-one.ts');
writeFileSync(editor, `import {readFileSync,writeFileSync} from 'node:fs';\nconst path=process.argv.at(-1);\nconst text=readFileSync(path,'utf8');\nconst replaced=text.replace(/^<<<<<<< [^\\n]*\\n[\\s\\S]*?^>>>>>>> [^\\n]*\\n/m,'resolved-start\\n');\nif(text===replaced) throw Error('No fixture conflict found');\nwriteFileSync(path,replaced);\n`);
jj(['--config', 'ui.editor=' + JSON.stringify([process.execPath, editor]), 'resolve', '--tool', ':editor', 'drawing.txt']);
const partialText = readFileSync(join(repo, 'drawing.txt'), 'utf8');
assert.equal((partialText.match(/^<<<<<<< /gm) || []).length, 1);
assert(partialText.startsWith('resolved-start\n'));
assert.equal(JSON.parse(log('json(conflict)').stdout), true);
record('noninteractive :editor preserves partial three-side resolution', { beforeHunks: 2, afterHunks: 1, unresolved: true, resolvedTextPreserved: true });
jj(['new', base, '-m', 'Fixture divergent source']);
const divergentSource = id();
const fork = op();
jj(['describe', '-r', divergentSource, '-m', 'Fixture version one']);
// Intentional operation forks only in this disposable fixture, never a recovery recipe.
jj(['--at-op=' + fork, 'describe', '-r', divergentSource, '-m', 'Fixture version two']);
const ambiguous = jj(['--ignore-working-copy', '--at-op=@', 'op', 'log', '-n', '1', '-G', '-T', 'id'], true);
assert.notEqual(ambiguous.status, 0);
record('ambiguous operation heads produce an error without merging', ambiguous);
jj(['status']); // Deliberately reconcile only the synthetic fixture's operation heads.
const divergent = JSON.parse(log('"[" ++ revset("mutable() & divergent()").map(|c| json({"change_id" => c.change_id(), "commit_id" => c.commit_id()})).join(",") ++ "]"', 'root()').stdout);
assert.equal(divergent.length, 2);
assert.equal(new Set(divergent.map((v: { change_id: string }) => v.change_id)).size, 1);
record('divergent versions differ from unique divergent changes', divergent);
jj(['new', base, '-m', 'Fixture bookmark observer']);
jj(['bookmark', 'create', 'delete-update', '-r', base]);
const bookmarkOp = op();
jj(['bookmark', 'set', 'delete-update', '-r', sides[0]]);
jj(['--at-op=' + bookmarkOp, 'bookmark', 'delete', 'delete-update']);
jj(['status']);
const bookmark = JSON.parse(jj(['--ignore-working-copy', '--at-op=@', 'bookmark', 'list', 'delete-update', '-T', 'if(!remote, json({"name" => name, "conflict" => conflict, "added_count" => added_targets.len(), "removed_count" => removed_targets.len()}))']).stdout);
const targets = JSON.parse(log('json(revset(' + JSON.stringify('bookmarks(exact:"delete-update")') + ').map(|c| c.commit_id()))', 'root()').stdout);
const nameLookup = jj(['--ignore-working-copy', '--at-op=@', 'log', '-r', 'delete-update', '-G', '-T', 'commit_id'], true);
assert(bookmark.conflict);
assert.equal(targets.length, 1);
assert.notEqual(nameLookup.status, 0);
record('bookmark delete/update conflict has one non-null target', { bookmark, targets, nameLookup });
const child = join(lab, 'child');
jj(['workspace', 'add', '--name', 'child', '-r', base, child]);
const common = id();
jj(['edit', common], false, child);
const workspaces = jj(['--ignore-working-copy', '--at-op=@', 'workspace', 'list', '-T', 'json({"name" => name, "current_workspace" => current_workspace, "target_is_current_commit" => target.current_working_copy()}) ++ "\\n"']).stdout.trim().split('\n').map(line => JSON.parse(line));
assert.equal(workspaces.filter(w => w.target_is_current_commit).length, 2);
assert.equal(workspaces.filter(w => w.current_workspace).length, 1);
record('workspace identity differs from shared commit identity', workspaces);
const invalidDestination = join(lab, 'invalid-destination');
const invalidWorkspace = jj(['workspace', 'add', '--name', 'invalid', '-r', 'missing-revision', invalidDestination], true);
assert.notEqual(invalidWorkspace.status, 0);
assert.match(invalidWorkspace.stderr, /Revision .*missing-revision.*doesn.t exist/);
assert.equal(existsSync(invalidDestination), false);
record('invalid workspace revision leaves no destination', invalidWorkspace);
const prepared = join(lab, 'prepared');
const callerBefore = log('commit_id').stdout;
writeFileSync(join(repo, 'unsaved-before-prepare.txt'), 'Unsnapshotted fixture data\n');
const oldPrepare = jj(['--ignore-working-copy', 'workspace', 'add', '--name', 'prepared', '--sparse-patterns', 'full', '--colocate', '-r', base, prepared], true);
assert.notEqual(oldPrepare.status, 0);
assert.match(oldPrepare.stderr, /Don't use --ignore-working-copy/);
assert.equal(existsSync(prepared), false);
record('INCOMPATIBILITY: current prepare recipe is rejected by 0.47.1', oldPrepare);
// The seemingly equivalent @ shorthand still snapshots the caller.
jj(['--at-op=@', 'workspace', 'add', '--name', 'prepared', '--sparse-patterns', 'full', '--colocate', '-r', base, '-m', 'Experimental prepare', prepared]);
assert.notEqual(log('commit_id').stdout, callerBefore);
assert.notEqual(jj(['--ignore-working-copy', '--at-op=@', 'file', 'list', 'unsaved-before-prepare.txt']).stdout, '');
record('UNSAFE replacement: --at-op=@ snapshots the caller', { callerCommitChanged: true, unsavedFileCaptured: true });
// Experimental exact-ID replacement; it needs lifecycle/concurrency qualification.
const exactPrepared = join(lab, 'exact-prepared');
const exactCallerBefore = log('commit_id').stdout;
const exactOperation = op();
writeFileSync(join(repo, 'unsaved-before-exact-prepare.txt'), 'Unsnapshotted fixture data\n');
jj(['--at-op=' + exactOperation, 'workspace', 'add', '--name', 'exact-prepared', '--sparse-patterns', 'full', '--colocate', '-r', base, '-m', 'Experimental exact prepare', exactPrepared]);
assert.equal(log('commit_id').stdout, exactCallerBefore);
assert.equal(jj(['--ignore-working-copy', '--at-op=@', 'file', 'list', 'unsaved-before-exact-prepare.txt']).stdout, '');
assert.equal(readFileSync(join(prepared, 'drawing.txt'), 'utf8'), 'base\n');
assert.equal(readFileSync(join(exactPrepared, 'drawing.txt'), 'utf8'), 'base\n');
assert.equal(jj(['--ignore-working-copy', '--at-op=@', 'log', '-r', '@-', '-G', '-T', 'commit_id'], false, exactPrepared).stdout, base);
record('candidate exact-operation prepare preserves caller and materializes child directly', { callerCommitUnchanged: true, callerDiskNotSnapshotted: true, childMaterialized: true, childParentMatchesBase: true });
console.log(JSON.stringify({ version, passed: checks.length, results: join(output, 'results.json'), fixture: lab }));
