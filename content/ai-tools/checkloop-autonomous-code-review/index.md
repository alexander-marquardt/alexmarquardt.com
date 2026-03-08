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

Claude Code is genuinely good at code review — better than many humans at spotting certain categories of bugs. But I kept running into the same frustrating loop. I'd ask it to review a codebase, it would find real issues and fix them, and I'd think we were done. Then I'd look at the code myself and immediately spot something obvious that it missed. So I'd ask it to review again, and it would catch *that* issue plus a few more — but miss yet another category entirely. Each time I thought the review was complete, another manual round would turn up more problems.

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

1. **Readability** — rename confusing variables, split long functions, improve comments. No behaviour changes.
2. **DRY** — find repeated logic, extract shared helpers, consolidate constants.
3. **Tests** — write missing tests, target >=90% coverage, run the suite and fix failures.
4. **Docs** — README, docstrings, config documentation.

**Thorough** (10 checks) — basic plus:

5. **Security** — injection vulnerabilities, hardcoded secrets, input validation, unsafe dependencies.
6. **Performance** — N+1 queries, blocking I/O, unnecessary allocations.
7. **Error handling** — try/except coverage, meaningful messages, logging.
8. **Type safety** — type annotations, replace `Any`/untyped code, run type checker.

**Exhaustive** (all 17 checks) — thorough plus:

9. **Edge cases** — off-by-one, null/empty inputs, overflow, Unicode edge cases.
10. **Complexity** — flatten nested conditionals, reduce cyclomatic complexity.
11. **Deps** — remove unused dependencies, flag vulnerable/outdated packages.
12. **Logging** — structured logging, request context, observability gaps.
13. **Concurrency** — race conditions, missing locks, async/await correctness.
14. **Accessibility** — semantic HTML, ARIA, keyboard nav, colour contrast (WCAG AA).
15. **API design** — consistent naming, HTTP methods, error formats, pagination.

Each check goes deep on one thing instead of shallow on everything.

## Two loops, not one

The tool has two levels of iteration. The **inner loop** runs each check in sequence — readability, then DRY, then tests, then security, and so on. Each check focuses on one dimension and builds on the cleanup of the previous one.

The **outer loop** (`--cycles`) repeats that entire sequence. Why? Because the first cycle's improvements create a new baseline. Code that was "clean enough" after cycle 1 now has new issues visible — the DRY check extracted a helper, but cycle 2's readability check notices the helper has a confusing name. Cycle 2's security check catches a validation gap that only appeared after cycle 1's refactoring.

With `--cycles 2`, the tool runs all selected checks, then runs them again on the improved codebase. Each cycle finds a diminishing but real set of issues that the previous cycle's fixes made visible.

### Skipping no-op checks

On cycle 2 and beyond, `checkloop` automatically skips any check that made no changes in the previous cycle. If the DRY check found nothing to extract in cycle 1, it won't run again in cycle 2. This avoids wasting time re-running checks that have already done their job. The bookend checks (test-fix and test-validate) always run on every cycle regardless, since new changes from other checks could introduce regressions.

### Convergence detection

When running multiple cycles, `checkloop` can stop early once the codebase stabilises. After each cycle it commits the changes and measures what percentage of total tracked lines were modified. If that percentage falls below the `--converged-at-percentage` threshold (default 0.1%), the loop exits. This prevents unnecessary cycles once the code has converged to a stable state.

```bash
# Run up to 5 cycles, but stop early if changes drop below 0.5%
uv run checkloop --dir ~/my-project --cycles 5 --converged-at-percentage 0.5
```

## Compounding improvements

Within a single cycle, the checks compound on each other:

1. The **readability** check renames a variable from `d` to `user_document` and splits a 120-line function into four smaller ones.
2. The **DRY** check now sees that two of those smaller functions are nearly identical and extracts a shared helper.
3. The **security** check catches that the shared helper doesn't validate its input — an injection risk that was invisible when the logic was duplicated across 120 lines.
4. The **tests** check writes tests against the now-clean API surface, achieving coverage that would have been painful to write against the original code.

Across cycles, the effect compounds further. The second cycle starts from a much cleaner codebase and consistently finds a second layer of issues that the first cycle couldn't see.

## Process management

Since `checkloop` is designed to run unattended for long periods (potentially hours with many checks and multiple cycles), it takes care to manage system resources:

- **Process group isolation** — each Claude Code subprocess runs in its own process group. When a check completes or times out, the entire group is killed (SIGTERM, then SIGKILL after 5 seconds), ensuring no orphaned Node.js processes accumulate.
- **Orphan scanning** — after every check, `checkloop` scans for surviving child processes and kills any that escaped the process group cleanup.
- **Idle timeout** — if Claude produces no output for 2 minutes (configurable with `--idle-timeout`), the process is killed and the next check begins. There's no hard wall-clock timeout — checks can run as long as they're making progress.
- **Memory reporting** — in verbose mode (`-v`), current RSS is logged after every check so you can monitor memory usage during long runs.

## The tool

I built [checkloop](https://github.com/alexander-marquardt/checkloop) — a single-module Python CLI that wraps Claude Code in an autonomous loop.

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
