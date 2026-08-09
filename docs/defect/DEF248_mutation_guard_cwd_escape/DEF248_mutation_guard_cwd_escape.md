# DEF248 — a `<test-cmd>` that changes directory defeats mutation_guard's revert

**Filed:** 2026-08-10 · **Source:** prompt · **Category:** process · **Status:** fixed · **Session:** AT:R66

## What happened

While proving CR162's new semantics-identifier guard was real, this ran:

```bash
scripts/mutation_guard.sh mobile/lib/widgets/hex/hex_bottom_nav.dart \
  "perl -0pi -e 's/      identifier: item\.id,\n//' mobile/lib/widgets/hex/hex_bottom_nav.dart" \
  "cd mobile && flutter test test/qa/semantics_ids_test.dart"
```

The mutation applied, the tests went red (correct — the guard works), and then:

```
── reverting
error: pathspec 'mobile/lib/widgets/hex/hex_bottom_nav.dart' did not match any file(s) known to git
```

**The mutation was left applied in the working tree.** The file sat with
`identifier: item.id` deleted, and nothing said so.

## Root cause

`eval "$TEST_CMD"` runs in the script's own shell, not a subshell. A test command
containing `cd mobile` therefore moves the *script's* working directory. Every
subsequent git call uses a repo-relative path (`mobile/lib/...`) which no longer
resolves from `mobile/`, so `git checkout -- "$TARGET"` fails.

The second-order problem is worse than the first. The script runs under
`set -euo pipefail`, so the failing `git checkout` **exits the script immediately** —
which means this, the check that exists precisely for the revert failing:

```bash
if ! git diff --quiet -- "$TARGET"; then
  fail "revert INCOMPLETE — '$TARGET' still differs from HEAD. ..."
fi
```

is unreachable dead code in the one situation it was written for. The script's own
"prove the revert was total by reading the tree, not by trusting the command" promise
does not hold.

## Why this matters more than the usual bug

This is `failure_patterns.md` **P9** — a verification procedure destroying its own
evidence — inside the script written to prevent P9. `mutation_guard.sh`'s header
documents DEF127 and DEF130, both of which were "the revert deleted something it
shouldn't have". This is the mirror: the revert didn't happen at all.

The failure is quiet. The operator sees `── test exit code under mutation: 1`, which
reads as "mutation caught", followed by a git error that looks like tidy-up noise. On
this run the next command happened to be a `git status`; a run that went straight to
`flutter test` would have reported a red suite against a silently mutated tree, or —
worse — the mutation would have been swept into the next commit. On a shared checkout
where other lanes commit by pathspec, that is exactly the class of thing that gets
attributed to the wrong track.

## Fix

`scripts/mutation_guard.sh`:

1. **Pin every git call to the repo root** — `git -C "$REPO_ROOT"`, resolved once at
   start. The script's cwd then cannot affect whether a revert lands.
2. **Run `$MUTATE` and `$TEST_CMD` in subshells** — `( eval "..." )` — so a `cd` in
   either cannot move the script at all.
3. **Do not let `set -e` skip the revert verification.** Capture the checkout's exit
   status instead of dying on it, then let the tree comparison be authoritative, which
   is what the script already claims to do.

Verified by re-running the original cd-containing command: the mutation is caught
(exit 1) *and* the tree is restored, and by an explicit regression check that a
`cd`-containing test command no longer leaves the target dirty.

## Related

- `docs/initial_specs/08_tech/failure_patterns.md` P9
- CR110 (built `mutation_guard.sh`), DEF127, DEF130, DEF136 (the three incidents it encodes)
- CR162 (the work that surfaced this)
