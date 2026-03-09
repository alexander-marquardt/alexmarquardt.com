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
description: "A Python tool that runs Claude Code in an autonomous, multi-check review loop with tiered depth and convergence detection."
---

Claude Code is genuinely good at code review — better than many humans at spotting certain categories of bugs. But I often experienced that it would find real issues and fix them, and I'd think we were done, but another check would reveal additional errors. So I'd ask it to review again, and it would catch *that* issue plus a few more — but miss yet another category entirely. Each time I thought the review was complete, another manual round would turn up more problems.

I found myself doing this over and over: review, spot what it missed, ask again, spot more, ask again. The code kept getting better with each round, but it took constant manual intervention to drive the process forward. After the fourth or fifth time doing this on a single project, I realized the iteration itself was the valuable part — and there was no reason I should be the one managing it by hand.

That's what led me to build `checkloop`. Instead of me sitting there cycling through review after review, the tool does it autonomously. And instead of asking Claude to look at "everything" each time, it breaks the review into focused, dimension-specific checks that compound on each other.

## The problem with "review everything"

When you ask an AI (or a human) to review code for everything at once — readability, security, test coverage, performance, error handling — each concern gets shallow attention. The model spreads itself thin. It catches the surface-level naming issues and maybe a missing null check, but it doesn't go deep on any single dimension.

Worse, some issues are invisible until you fix other issues first. A security vulnerability buried inside duplicated code across three files is nearly impossible to spot until you eliminate the duplication.

## Dimension-specific checks

The fix is simple: run multiple checks, each focused on a single concern.

There are 17 built-in checks (including two bookend checks that ensure the test suite is green before and after the review), organized into three tiers of increasing depth:

Every tier starts with a **test-fix** check (runs the existing test suite and fixes any failures) and ends with a **test-validate** check (re-runs the full suite to catch regressions introduced during review).

**Basic** (6 checks) — core code quality:

1. **Readability** — rename genuinely confusing variables (not marginal preference renames), split long functions, add module-level and class-level docstrings that explain design strategy and intent. No behaviour changes.
2. **DRY** — find repeated logic, extract shared helpers, separate mixed concerns into focused modules when it improves testability.
3. **Tests** — write behaviour-driven tests that verify correctness of complex logic (regex, parsing, validation), not just that code runs. Unit tests with mocks for external services, integration tests separately. Avoids testing impossible defensive paths.
4. **Docs** — README, config documentation. Module-level docstrings for design strategy, class docstrings for intent. Function docstrings only where name and signature don't tell the full story.

**Thorough** (10 checks) — basic plus:

5. **Security** — injection vulnerabilities, hardcoded secrets, input validation. Won't change CORS/retry/auth config without a clear vulnerability.
6. **Performance** — N+1 queries, O(N²) algorithms, blocking I/O, unnecessary allocations. Selective caching (`@cache`, `@lru_cache`) for expensive repeated computations like compiled regexes and config loading.
7. **Error handling** — centralized error handling for external services (shared helpers that log context and raise consistent errors). Only where code can meaningfully respond. No wrapping code that can't fail.
8. **Type safety** — type annotations, replace `Any`/untyped code, runtime validation at API boundaries (Annotated types, Pydantic, Zod). Run type checker.

**Exhaustive** (all 17 checks) — thorough plus:

9. **Edge cases** — off-by-one, null/empty inputs, overflow, Unicode edge cases.
10. **Complexity** — flatten nested conditionals, reduce cyclomatic complexity.
11. **Deps** — remove verified-unused dependencies, flag vulnerable/outdated packages.
12. **Logging** — structured logging at entry points. No debug logging on hot paths.
13. **Concurrency** — race conditions, missing locks, async/await correctness.
14. **Accessibility** — semantic HTML, ARIA, keyboard nav, colour contrast (WCAG AA).
15. **API design** — consistent naming, HTTP methods, error formats, pagination.

Each check goes deep on one thing instead of shallow on everything.

**On-demand:** There's also a `cleanup-ai-slop` check that's not part of any tier — it only runs when you explicitly request it with `--cleanup-ai-slop`. This is a remediation tool for codebases that have already accumulated AI-generated noise. It removes redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests, and reverts operational config changes that don't fix real vulnerabilities. It's designed to delete code, not add it.

## Two loops, not one

The tool has two levels of iteration. The **inner loop** runs each check in sequence — readability, then DRY, then tests, then security, and so on. Each check focuses on one dimension and builds on the cleanup of the previous one.

The **outer loop** (`--cycles`) repeats that entire sequence. Why? Because the first cycle's improvements create a new baseline. Code that was "clean enough" after cycle 1 now has new issues visible — the DRY check extracted a helper, but cycle 2's readability check notices the helper has a confusing name. Cycle 2's security check catches a validation gap that only appeared after cycle 1's refactoring.

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

## Avoiding AI-generated noise

One of the biggest risks with autonomous AI code review is that the tool generates _more_ code without generating _better_ code. After running `checkloop` on a real codebase and comparing the result to the original, several anti-patterns emerged:

- **Blanket docstrings** — adding docstrings to every function, even when the name and signature are self-documenting. Module-level docstrings explaining design strategy and class docstrings explaining intent _are_ valuable — the problem is function-level docstrings like "Get a user by their ID" on `get_user_by_id`.
- **Over-handling errors** — wrapping code in try/except when the wrapped call can't actually raise. Misleading error handling is worse than none.
- **Over-logging** — adding `logger.debug()` to every function entry, including hot paths like query builders, where it adds overhead for no diagnostic value.
- **Coverage-driven tests** — writing tests that pass `None` where the type says `str` (with `# type: ignore`) to test defensive paths that can't actually happen.
- **Rename churn** — renaming variables for marginal clarity, creating large diffs through hot paths for little improvement.
- **Breaking operational defaults** — tightening CORS settings or changing retry policies under the banner of "security" when there's no actual vulnerability.

Every check prompt in `checkloop` now includes explicit guardrails against these patterns. A global instruction prepended to all checks tells Claude to respect the existing codebase style, avoid blanket additions, and only make changes that are clearly justified. Individual checks reinforce this — the readability check says "don't rename for marginal gains", the error handling check says "only add try/except where code can meaningfully respond", the logging check says "don't log on hot paths", and so on.

These guardrails don't prevent all noise, but they significantly reduce it. The goal is that every change in the diff should be defensible on its own merits.

For codebases that already have accumulated AI slop, the `cleanup-ai-slop` check (run with `--cleanup-ai-slop`) actively finds and removes it — redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests, and reverted operational config changes.

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
- **Idle timeout** — if Claude produces no output for 5 minutes (configurable with `--idle-timeout`), the process is killed and the next check begins.
- **Hard check timeout** — optional wall-clock limit per check (`--check-timeout`), which kills even actively-running checks. Useful for CI or when you know no single check should take more than a certain amount of time.
- **Memory reporting** — in verbose mode (`-v`), current RSS and child process count are logged after every check so you can monitor resource usage during long runs.

## The tool

I built [checkloop](https://github.com/alexander-marquardt/checkloop) — a modular Python CLI that wraps Claude Code in an autonomous loop.

```bash
git clone https://github.com/alexander-marquardt/checkloop.git
cd checkloop && uv sync
```

Run with `uv run checkloop` from the cloned directory, and choose a check depth with `--level`:

```bash
# Basic tier (default): readability, DRY, tests, docs
uv run checkloop --dir ~/my-project

# Thorough: adds security, performance, error handling, type safety
uv run checkloop --dir ~/my-project --level thorough

# Exhaustive: all 17 checks, repeat twice
uv run checkloop --dir ~/my-project --level exhaustive --cycles 2

# Or pick specific checks manually
uv run checkloop --dir ~/my-project --checks readability security tests

# Clean up AI-generated code slop (on-demand, not part of any tier)
uv run checkloop --dir ~/my-project --cleanup-ai-slop

# Preview without running
uv run checkloop --dry-run
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

No. Similar approaches exist — LLMLOOP, SELF-REFINE, and various review-loop scripts. The idea of iterating on AI output isn't new. But `checkloop` is specifically designed for the "walk away and come back to better code" workflow: autonomous, multi-dimensional, with tiered depth, convergence detection, and live progress streaming.

## When to use it

I use it on feature branches before opening a PR. Point it at the branch, run two cycles with all checks, review the diff when it's done. It typically takes 20-40 minutes for a medium-sized project (a few thousand lines), and I consistently find that the resulting code is cleaner than what I'd produce with manual review alone.

It's not a replacement for human review. It's the first round that makes human review more productive.

The repo is at [github.com/alexander-marquardt/checkloop](https://github.com/alexander-marquardt/checkloop). MIT licensed.
