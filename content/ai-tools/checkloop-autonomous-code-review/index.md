---
showtoc: true
title: "Autonomous Multi-Check AI Code Review"
date: 2026-03-07
draft: false
slug: checkloop-autonomous-code-review
aliases:
  - /ai-tools/claudeloop-autonomous-code-review/
tags: ["ai", "code-review", "developer-tooling", "claude"]
categories: ["AI-Assisted Development"]
description: "A Python tool that runs Claude Code in an autonomous, multi-check review loop with three levels of review thoroughness, cross-check coherence validation, and convergence detection."
---

Claude Code is genuinely good at code review — better than many humans at spotting certain categories of bugs. But I often experienced that it would find real issues and fix them, and I'd think we were done, but another check would reveal additional errors. So I'd ask it to review again, and it would catch *that* issue plus a few more — but miss yet another category entirely. Each time I thought the review was complete, another manual round would turn up more problems.

I found myself doing this over and over: review, spot what it missed, ask again, spot more, ask again. The code kept getting better with each round, but it took constant manual intervention to drive the process forward. After the fourth or fifth time doing this on a single project, I realized the iteration itself was the valuable part — and there was no reason I should be the one managing it by hand.

That's what led me to build `checkloop`. Instead of me sitting there cycling through review after review, the tool does it autonomously. And instead of asking Claude to look at "everything" each time, it breaks the review into focused, dimension-specific checks that compound on each other.

## The problem with "review everything"

When you ask an AI (or a human) to review code for everything at once — readability, security, test coverage, performance, error handling — each concern gets shallow attention. The model spreads itself thin. It catches the surface-level naming issues and maybe a missing null check, but it doesn't go deep on any single dimension.

Worse, some issues are invisible until you fix other issues first. A security vulnerability buried inside duplicated code across three files is nearly impossible to spot until you eliminate the duplication.

## Dimension-specific checks

The fix is simple: run multiple checks, each focused on a single concern.

There are 32 built-in checks (including two bookend checks that ensure the test suite is green before and after the review), organized into four execution plans of increasing depth:

Every plan starts with a **test-fix** check (runs the existing test suite and fixes any failures) and ends with a **test-validate** check (re-runs the full suite to catch regressions introduced during review).

**Basic** (5 checks) — core code quality:

1. **Readability** — rename genuinely confusing variables (not marginal preference renames), split long functions. Will not add docstrings or comments to code it didn't change — only documents code that is genuinely confusing without explanation. No behaviour changes.
2. **DRY** — find repeated logic, extract shared helpers, separate mixed concerns into focused modules when it improves testability.
3. **Tests** — write behaviour-driven tests that verify correctness of complex logic (regex, parsing, validation), not just that code runs. Unit tests with mocks for external services, integration tests separately. Avoids testing impossible defensive paths.

**Thorough** (15 checks) — basic plus:

4. **Docs** — README, config documentation. The bar for adding docstrings is high: only where name and signature leave genuine ambiguity (complex return values, non-obvious side effects, surprising semantics). When in doubt, leaves the code undocumented.
5. **Docs accuracy** — cross-references CLI `--help` text, README examples, error messages, and API docs against actual code behavior. Fixes factual inaccuracies (wrong defaults, renamed flags, stale file paths) without adding new documentation.
6. **Security** — injection vulnerabilities, hardcoded secrets, input validation. Won't change CORS/retry/auth config without a clear vulnerability.
7. **Performance** — N+1 queries, O(N²) algorithms, blocking I/O, unnecessary allocations. Selective caching (`@cache`, `@lru_cache`) for expensive repeated computations like compiled regexes and config loading.
8. **Error handling** — centralized error handling for external services (shared helpers that log context and raise consistent errors). Only where code can meaningfully respond. No wrapping code that can't fail.
9. **Type safety** — type annotations, replace `Any`/untyped code, runtime validation at API boundaries (Annotated types, Pydantic, Zod). Run type checker.
10. **Derived values** — finds frontend code that re-derives values the backend already computes. Totals, permissions, status flags, formatted labels — if the backend computed it, the frontend should consume it from an existing API response, not recalculate it independently. If the value isn't in the response yet, the fix is to add it there — not to create new API calls or recompute on the frontend. Trivially deterministic computations (like `items.length`) are excluded.
11. **Architecture boundaries** — discovers the project's architectural layers (frontend/backend, standalone library/application, API/service/data), checks that dependencies flow in one direction, and fixes violations. Handles upward imports, leaking internals, shared state coupling, mixed-layer modules, and circular dependencies. Skips single-layer projects where there's nothing to enforce.
12. **Coherence** — reviews the codebase as a whole after all other checks and fixes cases where checks worked against each other. Catches conflicting changes (error handling added then partially stripped), cumulative over-engineering (each check added a small abstraction but together they're worse than the original), style drift away from project conventions, redundant layering from multiple checks addressing the same concern, and broken call chains from refactors that weren't fully propagated.

**Exhaustive** (all 23 checks) — thorough plus:

13. **Edge cases** — off-by-one, null/empty inputs, overflow, Unicode edge cases.
14. **Complexity** — flatten nested conditionals, reduce cyclomatic complexity.
15. **Deps** — remove verified-unused dependencies, flag vulnerable/outdated packages.
16. **Logging** — structured logging at entry points. No debug logging on hot paths.
17. **Concurrency** — race conditions, missing locks, async/await correctness.
18. **Concurrency test coverage** — flags multi-user projects (web apps, APIs, e-commerce) that lack tests simulating concurrent access to shared state. Writes correctness-under-concurrency tests for critical operations like inventory decrement, balance transfers, and seat reservations. Verifies atomicity, idempotency, and database-level protections under parallel access. Skips single-user projects where concurrency testing doesn't apply.
19. **Accessibility** — semantic HTML, ARIA, keyboard nav, colour contrast (WCAG AA).
20. **API design** — consistent naming, HTTP methods, error formats, pagination.
21. **Cleanup slop** — removes unnecessary noise accumulated by earlier checks: redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests.

**Super-exhaustive** (all 32 checks) — everything in exhaustive plus a set of infrastructure and hygiene audits that are too slow or too project-specific to run on every pass:

22. **Check-config** — audits whether the project's test, lint, type-check, and CI infrastructure matches its stack. Scaffolds Playwright for web apps missing E2E coverage, wires up coverage gates, and ensures CI runs the tools that exist locally. This is the structural check that would have caught "React frontend but no browser test runner installed" — a class of gap the behavioural `tests` check can't close on its own.
23. **Dead code** — unused exports, orphaned files, unreachable branches, stale feature-flag references, and old commented-out blocks. Uses `ts-prune`/`vulture`/`staticcheck` where available.
24. **Observability** — auth, payments, data mutations, external API calls, and background jobs should have structured logs, metrics, and a path to an alerting channel. Adds what's missing using the project's existing observability stack — won't introduce a new one.
25. **Schema validation** — every external boundary (HTTP handlers, webhooks, queue consumers, external API responses, env/config) must parse through a schema (Zod/Pydantic/etc.), not a raw type assertion. Verifies webhook signature checks.
26. **Secret leakage** — scans the repo and built output for API keys, tokens, private keys, connection strings with embedded passwords, PII in logs, and server secrets bundled into client JavaScript. Flags commits that need rotation.
27. **Migration safety** — reviews database migrations for locking risk, concurrent-index creation, destructive-change staging (expand-and-contract vs one-step DROPs), chunked backfills, rollback paths, and transaction-boundary correctness.
28. **Feature flags** — ghost flags (referenced in code but no longer defined), orphan flags (defined but never checked), fully-rolled-out flags with dormant branches, and conflicting flag gates.
29. **Fixture drift** — test mocks and recorded fixtures that no longer match the real code or external APIs. Catches silently-passing mocks, deep-chain patches, stale HTTP recordings, and leaking mocks without teardown.
30. **Meta-review** — the last check in the plan. Reads the codebase and the full set of existing checks, then writes `.checkloop-recommendations.md` with prioritised suggestions for domain-specific checks or tests that the generic suite doesn't cover. Makes no code changes. The report is printed to the terminal at the end of the run so recommendations are the last thing you see.

The super-exhaustive plan is intentionally not the default — it's meant for occasional deep audits, not every pre-push pass. The meta-review at the end is what makes it worth running periodically: even when the preceding 31 checks don't produce many changes, meta-review frequently surfaces project-specific gaps (tenant-isolation tests, rate-limit regression tests, domain-invariant checks) that generic dimensions miss.

Each check goes deep on one thing instead of shallow on everything.

### Fully file-based architecture

Every part of checkloop's behavior is defined in editable files at the project root — no Python changes needed to customize:

- **`checks/`** — one Markdown file per check. Each has YAML frontmatter (`id`, `label`) and a prompt body. Edit a prompt, add a new check, or remove one by modifying files.
- **`execution_plans/`** — TOML files that define which checks to run and which model for each. Three ship pre-populated (basic, thorough, exhaustive).
- **`prompt_templates/`** — boilerplate injected into every check at runtime: the scope prefix (review all code vs changed files) and commit message rules.

To add a new check, create a Markdown file in `checks/` and reference its ID in a plan TOML. To customize a prompt, edit the `.md` file directly.

### Per-check model selection

Not all checks have the same cognitive demands. A readability check is mostly pattern matching — rename this confusing variable, split this long function — and Sonnet handles it quickly and cleanly. But a security check needs to trace injection paths across a frontend router, a service layer, and a database query. A concurrency check needs to reason about race conditions spanning multiple threads and lock orderings. These require Opus's deeper multi-layer analysis.

Each plan file specifies which model to use for each check. The pre-populated plans route 14 of 21 checks to Sonnet and 7 to Opus:

- **Opus** for: `security`, `concurrency`, `concurrency-testing`, `perf`, `edge-cases`, `architecture-boundaries`, `coherence` — checks where subtle issues span multiple code layers and require multi-step reasoning.
- **Sonnet** for everything else — pattern-matching tasks where Sonnet is faster and produces cleaner results.

The `--model` flag overrides this per-check assignment for all checks. Use `--model opus` to force deep analysis everywhere (slower), or `--model sonnet` for the fastest possible pass.

Plans are just TOML files — three ship pre-populated (basic, thorough, exhaustive), but you can write your own with whatever checks and model assignments fit your project. For example, a security-focused plan:

```toml
[tier]
name = "security-audit"
description = "Deep security analysis"

[[checks]]
id = "test-fix"
model = "sonnet"

[[checks]]
id = "security"
model = "opus"

[[checks]]
id = "concurrency"
model = "opus"

[[checks]]
id = "edge-cases"
model = "opus"

[[checks]]
id = "test-validate"
model = "sonnet"
```

```bash
uv run checkloop --dir ~/my-project --plan ./security-audit.toml
```

## Clone-by-default: don't touch the working tree

An early version of checkloop wrote directly into the user's working copy. That's fine when you know what you're getting into, but it meant you couldn't keep coding while checkloop ran — any edits you made would race against the tool's edits, and interrupting a run could leave your branch in a half-reviewed state.

The current default avoids this entirely. When you pass `--review-branch <ref>`, checkloop:

1. Makes a hardlink-backed `git clone --local` of `--dir` into `~/checkloop-runs/<project>-<iso-timestamp>/`. On the same filesystem this is effectively free — only uniquely modified objects consume disk.
2. Runs `git fetch origin --prune` inside the clone, then checks out the requested ref (preferring `origin/<ref>` over any local branch of the same name) in **detached-HEAD** state, so commits can't accidentally follow an upstream back to the remote.
3. Creates a named scratch branch — `<review-branch>-cl-<iso-timestamp>` (e.g. `main-cl-2026-04-21T10-30-45Z`) — and commits every change there.
4. On completion (or interrupt) prints copy-pasteable commands for adopting the scratch branch into your real repo via `git fetch <clone-dir> <branch>`, merging or cherry-picking it, or discarding everything with `rm -rf <clone-dir>`.

The practical consequence is that you can kick off a multi-cycle exhaustive run and keep working in the original checkout — different commits, different branches, different worktree — and the two don't collide. The clone directory is also a timestamped backup: if a check does something surprising, the pre-run state of the repo is preserved in the clone's git history until you delete it. Clones older than 14 days are pruned automatically the next time checkloop starts.

`--in-place` restores the old behaviour for cases where the clone is in the way: reviewing in-flight uncommitted work, running on non-git directories, or just wanting to see changes show up in the editor you already have open. In that mode the scratch branch is still created (named `checkloop-<iso-timestamp>`) but it lives inside the target repo.

### After a run: review, push, open a PR

checkloop deliberately stops once the scratch branch exists. It does not push, does not open a PR, does not merge. Those are decisions you make after looking at the diff — the tool has been wrong often enough that "review before adopting" is the default policy, not an optional step.

The post-run terminal output is a numbered checklist for exactly that flow. In clone mode it prints:

1. **Review the diff.** `git -C <clone-dir> log --oneline <base>..<branch>` for the shape of the changes, then `git -C <clone-dir> diff <base>..<branch>` for the substance. Read it. Autonomous checks occasionally rename a variable for the worse, over-handle an error that couldn't happen, or strip a comment that was load-bearing — you will catch these by looking.
2. **Optional second-opinion pass with Claude.** `cd <clone-dir> && claude "Review the diff between <base> and HEAD on this branch. Flag anything that looks incorrect, risky, or lower quality than the original."` A fresh Claude session reading the completed diff spots things the in-loop checks missed: each check was focused on one dimension and never saw the combined effect. This is the single most valuable optional step.
3. **Fetch the branch into your real repo.** `cd <your-repo> && git fetch <clone-dir> <branch>:<branch>`. The clone directory is a valid git remote path, so this Just Works and nothing touches `origin`.
4. **Push and open a PR targeting the branch you reviewed.** `git push -u origin <branch>` then `gh pr create --base <review-branch> --head <branch>`. The PR is where CI runs, where teammates comment on individual hunks, where the commit history lands in a form your project already knows how to handle.
5. **Merge through your normal PR workflow.** checkloop does not merge for you. If the PR passes review and CI, you merge it the same way you merge anything else.

In `--in-place` mode the scratch branch already lives in your repo, so you skip the local fetch in step 3 — everything else is the same. If you want to adopt changes without a PR, `git merge --ff-only <branch>` or a targeted `git cherry-pick` are available as alternatives. If you want to discard everything, `rm -rf <clone-dir>` (clone mode) or `git branch -D <branch>` (in-place) gets you back to where you started.

The point of printing this every run is that "what do I do now?" should not require re-reading the docs after the tool has been running unattended for an hour. The commands are already filled in with the real branch names and paths, ready to paste.

## Two levels of iteration

The tool iterates at two levels. The **inner level** runs each check in sequence — readability, then DRY, then tests, then security, and so on. Each check focuses on one dimension and builds on the cleanup of the previous one.

The **outer level** (`--cycles`) repeats that entire sequence. Why? Because the first cycle's improvements create a new baseline. Code that was "clean enough" after cycle 1 now has new issues visible — the DRY check extracted a helper, but cycle 2's readability check notices the helper has a confusing name. Cycle 2's security check catches a validation gap that only appeared after cycle 1's refactoring.

With `--cycles 2`, the tool runs all selected checks, then runs them again on the improved codebase. Each cycle finds a diminishing but real set of issues that the previous cycle's fixes made visible.

### Every check runs every cycle

All checks run on every cycle — nothing is skipped. Earlier checks routinely create work for later ones: a readability rename reveals duplication for the DRY check, a security fix introduces a new code path that needs error handling, a performance refactor changes an API that needs updated tests. Skipping checks that "did nothing last time" would miss these cascading improvements. Convergence detection (below) handles the case where there's genuinely nothing left to do.

### Convergence detection

When running multiple cycles, `checkloop` can stop early once the codebase stabilises. After each cycle it measures what percentage of total tracked lines were modified. If that percentage falls below the `--convergence-threshold` threshold (default 0.1%), the loop exits. This prevents unnecessary cycles once the code has converged to a stable state.

```bash
# Run up to 5 cycles, but stop early if changes drop below 0.5%
uv run checkloop --dir ~/my-project --cycles 5 --convergence-threshold 0.5
```

## Compounding improvements

Within a single cycle, the checks compound on each other:

1. The **readability** check renames a variable from `d` to `user_document` and splits a 120-line function into four smaller ones.
2. The **DRY** check now sees that two of those smaller functions are nearly identical and extracts a shared helper.
3. The **security** check catches that the shared helper doesn't validate its input — an injection risk that was invisible when the logic was duplicated across 120 lines.
4. The **tests** check writes tests against the now-clean API surface, achieving coverage that would have been painful to write against the original code.

Across cycles, the effect compounds further. The second cycle starts from a much cleaner codebase and consistently finds a second layer of issues that the first cycle couldn't see.

## Why incremental checks matter for large codebases

Claude has a finite context window. A project with thousands of files can't fit all at once. If you ask Claude to "review everything", it has to read hundreds of files before making a single edit — filling context with code it may never need while leaving no room for the actual work. I've watched this happen: Claude reads 15 files, context fills up, and it stalls in extended thinking without producing any edits.

Each checkloop check operates incrementally: read a handful of related files, make focused edits, commit, move on. The check-specific prompts guide Claude toward this pattern rather than attempting a full codebase scan. A readability check might read one module, improve its naming, commit the changes, and move to the next — instead of cataloguing every variable name in the project before touching anything. This keeps context available for reasoning and editing rather than exhausting it on upfront indexing.

The result is that checkloop scales to projects that would otherwise stall a single-pass review. A 50K-line codebase that times out when you ask Claude to "review it all" becomes manageable when broken into focused, incremental passes. Each check makes progress on a bounded scope before context pressure builds up, and the suite-level orchestration ensures every part of the codebase eventually gets attention.

## Avoiding AI-generated noise

One of the biggest risks with autonomous AI code review is that the tool generates _more_ code without generating _better_ code. After running `checkloop` on a real codebase and comparing the result to the original, several anti-patterns emerged:

- **Blanket docstrings** — adding docstrings to every function, even when the name and signature are self-documenting. A docstring saying "Get a user by their ID" on `get_user_by_id` is noise, not documentation.
- **Over-handling errors** — wrapping code in try/except when the wrapped call can't actually raise. Misleading error handling is worse than none.
- **Over-logging** — adding `logger.debug()` to every function entry, including hot paths like query builders, where it adds overhead for no diagnostic value.
- **Coverage-driven tests** — writing tests that pass `None` where the type says `str` (with `# type: ignore`) to test defensive paths that can't actually happen.
- **Rename churn** — renaming variables for marginal clarity, creating large diffs through hot paths for little improvement.
- **Breaking operational defaults** — tightening CORS settings or changing retry policies under the banner of "security" when there's no actual vulnerability.

Every check prompt includes explicit guardrails against these patterns. A global instruction prepended to all checks tells Claude not to add docstrings, comments, or type annotations to code it didn't otherwise change, and to leave well-named code undocumented. Individual checks reinforce this — the readability check says "don't rename for marginal gains" and "don't add docstrings to code you didn't change", the error handling check says "only add try/except where code can meaningfully respond", the logging check says "don't log on hot paths", and so on.

The `docs` check itself was moved out of the default basic plan into thorough — most clean codebases don't need a blanket documentation pass, and when they do, users can opt in explicitly. When `docs` does run, it operates with a high bar: only add a docstring when name and signature leave genuine ambiguity.

These guardrails don't prevent all noise, but they significantly reduce it. The goal is that every change in the diff should be defensible on its own merits.

For codebases that have accumulated this kind of noise, the `cleanup-ai-slop` check actively finds and removes it — redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests, and reverted operational config changes. It runs automatically as part of the exhaustive plan, or you can add it to any plan with `--plan thorough --checks cleanup-ai-slop`. Importantly, the check's commit messages and code comments use neutral language ("removed redundant docstrings", not "removed AI-generated slop") — no fingerprints left in the git history.

## Run summaries

After each cycle, `checkloop` prints a summary table showing per-check results — exit codes, kill reasons, lines changed, and duration. In multi-cycle runs, an overall summary at the end aggregates per-cycle totals so you can immediately see whether the number of changes is decreasing (converging) or increasing (diverging):

```
────────────────────────────────────────────────────────────────────────
  Overall Summary
────────────────────────────────────────────────────────────────────────

  Cycle  Checks    OK  Fail  Kill    Lines  Changed  Duration
  ─────  ──────  ────  ────  ────  ───────  ───────  ────────
      1       6     6     0     0      482    5/6     12m30s
      2       6     6     0     0      156    4/6      9m15s
      3       6     6     0     0       28    2/6      6m42s

  Total cycles : 3
  Total checks : 18  (18 ok, 0 failed, 0 killed)
  Total lines  : 666
  Elapsed      : 28m27s
```

The lines column shows green when decreasing and yellow when increasing. All output is also written to `.checkloop-run.log` at DEBUG level for post-run analysis.

## Per-check commits

Each check commits its changes individually rather than squashing all changes from a cycle into one commit. This makes it easy to see exactly what each check did when reviewing the git history, and to revert a specific check's changes without losing the rest of the cycle's work.

## Checkpoint & resume

Long runs get interrupted — you close your laptop, the terminal crashes, or you Ctrl+C because you need the machine for something else. Rather than restarting from scratch, `checkloop` saves a checkpoint after every completed check. On the next run, it detects the incomplete session and asks whether to pick up where it left off:

```
Previous incomplete run detected:
  Started     : 2026-03-08T14:30:00+00:00
  Progress    : cycle 1/2, check 3/6 completed
  Next check  : tests

  Resume from checkpoint? [y/N] (defaulting to N in 10s):
```

If you don't respond within 10 seconds (useful for unattended restarts), it starts fresh. The checkpoint file is cleaned up automatically on successful completion. Use `--no-resume` to skip the prompt entirely.

## Process management

Since `checkloop` is designed to run unattended for long periods (potentially hours with many checks and multiple cycles), it takes care to manage system resources:

- **Process group isolation** — each Claude Code subprocess runs in its own process group. When a check completes or times out, the entire group is killed (SIGTERM, then SIGKILL after 5 seconds), ensuring no orphaned Node.js processes accumulate.
- **Session-based cleanup** — after killing the process group, `checkloop` scans the session for any stragglers that escaped the group (e.g. processes that called `setsid()`). An atexit handler sweeps all tracked sessions on program exit, including on SIGTERM and SIGHUP.
- **Memory limit** — the child process tree's total RSS is sampled every 10 seconds. If it exceeds the `--max-memory-mb` limit (default 8192MB), the entire process group is killed immediately. This prevents runaway test suites or language servers from consuming all system memory.
- **Host-wide pressure floor** — a separate safety net, `--system-free-floor-mb` (default 500MB), kills the running check if free system memory drops below that threshold regardless of checkloop's own tree size. This catches the nastiest failure mode: swap thrash severe enough to require a hard reboot, where you'd rather lose one check than the whole machine.
- **Idle timeout** — if Claude produces no output for 5 minutes (configurable with `--idle-timeout`), the process is killed and the next check begins.
- **Hard check timeout** — optional wall-clock limit per check (`--check-timeout`), which kills even actively-running checks. Useful for CI or when you know no single check should take more than a certain amount of time.
- **Top-offender alerts** — when any of the kill paths fire, the log emits a one-line callout naming the single largest process in the tree: `→ top offender: pid=54321 rss=6821MB cmd=node .../claude-code`. When a kill is unexpected, that line is almost always the answer — usually a single language server or test worker, not the whole tree.
- **Memory reporting** — in verbose mode (`-v`), current RSS and child process count are logged after every check so you can monitor resource usage during long runs.

## Observability for stalls and OOMs

Long autonomous runs fail in ways that are hard to diagnose after the fact. The terminal is gone, the shell buffer is gone, and the in-memory log went with it. The only useful artifacts are the ones that were already written to disk before the crash.

checkloop writes two of those.

### A telemetry timeline that survives crashes

A background thread samples the process tree every ~3 seconds and appends one JSON line per sample to `<run-dir>/.checkloop-telemetry/telemetry-YYYY-MM-DD.jsonl` — where `<run-dir>` is the per-run directory under `~/checkloop-runs/` (clone mode) or the project root (`--in-place`). Each line captures parent RSS, total child-tree RSS, the top 5 processes by RSS (with pid and command), system free memory, swap usage, and which check was running at that moment.

The file is flushed and fsynced on every write, and lives alongside the per-run `.checkloop-run.log`. So when things go wrong, the timeline is intact:

```bash
# What was running when the kill fired?
tail -20 ~/checkloop-runs/myproj-2026-04-17T08-00-00Z/.checkloop-telemetry/telemetry-2026-04-17.jsonl | jq .

# Child-tree RSS over time, alongside the top process at each point
jq -r '[.iso, .children_rss_mb, (.top_children[0] // {}) | .cmd] | @tsv' \
  ~/checkloop-runs/myproj-2026-04-17T08-00-00Z/.checkloop-telemetry/telemetry-2026-04-17.jsonl
```

Retention is automatic — files older than 14 days are pruned, and the directory is capped at 200 MB, so it can't grow without bound. In `--in-place` mode the directory is git-ignored by default; in clone mode it lives outside the reviewed tree entirely.

This came directly out of a bad afternoon debugging a memory-kill bug where the terminal itself was dying mid-investigation. Without an on-disk timeline there was nothing to work from the next time I opened a shell. Now there is.

### A cleanup-time snapshot in `$HOME`

On any process-tree cleanup path — check end, timeout, memory kill, atexit — a one-line state snapshot is appended to `~/.checkloop/cleanup-debug.log`:

```
2026-04-17T08:10:37  pid=29897 ppid=29880 sessions=[29897] descendants=[29910, 29914, 29918]
```

It lives in `$HOME`, not the project workdir, so it survives a `rm -rf` of the project, outlives any single run, and is readable from a fresh terminal after a crash. The point is forensic: when you come back to a machine and don't know what happened, this file tells you what the process tree looked like at the moment of the last cleanup, so you can reconstruct whether the kill reached everything it was supposed to.

### Inline signals during silent work

Not every diagnostic needs to wait for a post-mortem. Claude routinely goes silent for minutes while a subprocess runs — a large `pytest` suite, a build, a `grep` over a huge repo. The natural question, staring at a blank screen, is "is this stuck or is it working?"

After about 15 seconds of silence, checkloop replaces the blank with an updating status line that shows elapsed time, what tool is running (e.g. *running pytest*), tree RSS, the current top process by RSS, and host free memory. A healthy long-running subprocess looks visibly healthy: RSS ticks up, top process is `pytest` or `python`, free memory is stable. A stalled one looks different immediately, and you stop reaching for Ctrl+C prematurely.

Together these three signals — the JSONL timeline, the cleanup snapshot, and the live status line — cover the full arc of what can go wrong: watching a run in progress, diagnosing a kill just after it fires, and reconstructing a crash days later.

## The tool

I built [checkloop](https://github.com/alexander-marquardt/checkloop) — a modular Python CLI that wraps Claude Code in an autonomous loop.

```bash
git clone https://github.com/alexander-marquardt/checkloop.git
cd checkloop && uv sync
```

Run with `uv run checkloop` from anywhere. Both `--dir` and a mode flag are required — either `--review-branch <ref>` (clone mode) or `--in-place`:

```bash
# Basic plan (default) — review origin/main in a disposable clone
uv run checkloop --dir ~/my-project --review-branch main

# Thorough: adds security (opus), perf (opus), docs, errors, types
uv run checkloop --dir ~/my-project --review-branch main --plan thorough

# Exhaustive: all 23 checks with optimized model assignments, repeat twice
uv run checkloop --dir ~/my-project --review-branch main --plan exhaustive --cycles 2

# Super-exhaustive: exhaustive plus 8 infrastructure audits and a final
# meta-review that writes recommendations for checks/tests specific to
# your project. Meant for occasional deep audits.
uv run checkloop --dir ~/my-project --review-branch main --plan super-exhaustive

# Review a feature branch from origin
uv run checkloop --dir ~/my-project --review-branch feature/my-work --plan thorough

# Or pick specific checks manually
uv run checkloop --dir ~/my-project --review-branch main --checks readability security tests

# Add a check on top of a plan
uv run checkloop --dir ~/my-project --review-branch main --plan thorough --checks cleanup-ai-slop

# Use your own plan file
uv run checkloop --dir ~/my-project --review-branch main --plan ./my-plan.toml

# Force all checks to opus for deeper analysis (slower)
uv run checkloop --dir ~/my-project --review-branch main --plan thorough --model opus

# Use a different Claude CLI executable (e.g. Bedrock-backed, no rate limits)
uv run checkloop --dir ~/my-project --review-branch main --claude-command claude-bedrock

# Run against the working tree directly (legacy mode) — no clone, reviews
# uncommitted changes too
uv run checkloop --dir ~/my-project --in-place

# Preview without running
uv run checkloop --dir ~/my-project --review-branch main --dry-run
```

To make `checkloop` available globally (without `uv run`):

```bash
uv tool install git+https://github.com/alexander-marquardt/checkloop.git
```

It streams progress in real time so you can see what Claude is reading, editing, and running:

```
[2m15s] [Read] src/api/handlers.py
[2m30s] [Edit] src/api/handlers.py
[3m01s] [Bash] $ pytest tests/ -x
[4m12s] [Write] tests/test_handlers.py
```

Use `-v` to see operational events and timing, or `--debug` for raw subprocess output.

## Is this novel?

No. Similar approaches exist — LLMLOOP, SELF-REFINE, and various review-loop scripts. The idea of iterating on AI output isn't new. But `checkloop` is specifically designed for the "walk away and come back to better code" workflow: autonomous, multi-dimensional, with configurable review levels, convergence detection, and live progress streaming.

## Token usage (Be Careful!!!)

Each check is a full Claude Code session — reading files, making edits, running tests. A basic plan run (5 checks) on a medium-sized project typically uses 200K–500K tokens. Thorough (15 checks) or exhaustive (23 checks) with multiple cycles can easily reach several million tokens. Multi-cycle exhaustive runs on large codebases can burn through a significant portion of a daily API budget.

I often kick off runs right before bed or when stepping away from the keyboard. The tool is designed to run unattended, but can burn through a lot of tokens. Pay attention to your token useage.

## When to use it

I use it on feature branches before opening a PR. Point it at the branch, run two cycles with all checks, review the diff when it's done. It typically takes 20-40 minutes for a medium-sized project (a few thousand lines), and I consistently find that the resulting code is cleaner than what I'd produce with manual review alone.

It's not a replacement for human review. It's the first round that makes human review more productive.

The repo is at [github.com/alexander-marquardt/checkloop](https://github.com/alexander-marquardt/checkloop). MIT licensed.
