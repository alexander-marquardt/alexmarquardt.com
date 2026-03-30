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
description: "A Python tool that runs Claude Code in an autonomous, multi-check review loop with three levels of review thoroughness and convergence detection."
---

Claude Code is genuinely good at code review — better than many humans at spotting certain categories of bugs. But I often experienced that it would find real issues and fix them, and I'd think we were done, but another check would reveal additional errors. So I'd ask it to review again, and it would catch *that* issue plus a few more — but miss yet another category entirely. Each time I thought the review was complete, another manual round would turn up more problems.

I found myself doing this over and over: review, spot what it missed, ask again, spot more, ask again. The code kept getting better with each round, but it took constant manual intervention to drive the process forward. After the fourth or fifth time doing this on a single project, I realized the iteration itself was the valuable part — and there was no reason I should be the one managing it by hand.

That's what led me to build `checkloop`. Instead of me sitting there cycling through review after review, the tool does it autonomously. And instead of asking Claude to look at "everything" each time, it breaks the review into focused, dimension-specific checks that compound on each other.

## The problem with "review everything"

When you ask an AI (or a human) to review code for everything at once — readability, security, test coverage, performance, error handling — each concern gets shallow attention. The model spreads itself thin. It catches the surface-level naming issues and maybe a missing null check, but it doesn't go deep on any single dimension.

Worse, some issues are invisible until you fix other issues first. A security vulnerability buried inside duplicated code across three files is nearly impossible to spot until you eliminate the duplication.

## Dimension-specific checks

The fix is simple: run multiple checks, each focused on a single concern.

There are 18 built-in checks (including two bookend checks that ensure the test suite is green before and after the review), organized into three execution plans of increasing depth:

Every plan starts with a **test-fix** check (runs the existing test suite and fixes any failures) and ends with a **test-validate** check (re-runs the full suite to catch regressions introduced during review).

**Basic** (5 checks) — core code quality:

1. **Readability** — rename genuinely confusing variables (not marginal preference renames), split long functions. Will not add docstrings or comments to code it didn't change — only documents code that is genuinely confusing without explanation. No behaviour changes.
2. **DRY** — find repeated logic, extract shared helpers, separate mixed concerns into focused modules when it improves testability.
3. **Tests** — write behaviour-driven tests that verify correctness of complex logic (regex, parsing, validation), not just that code runs. Unit tests with mocks for external services, integration tests separately. Avoids testing impossible defensive paths.

**Thorough** (11 checks) — basic plus:

4. **Docs** — README, config documentation. The bar for adding docstrings is high: only where name and signature leave genuine ambiguity (complex return values, non-obvious side effects, surprising semantics). When in doubt, leaves the code undocumented.
5. **Security** — injection vulnerabilities, hardcoded secrets, input validation. Won't change CORS/retry/auth config without a clear vulnerability.
6. **Performance** — N+1 queries, O(N²) algorithms, blocking I/O, unnecessary allocations. Selective caching (`@cache`, `@lru_cache`) for expensive repeated computations like compiled regexes and config loading.
7. **Error handling** — centralized error handling for external services (shared helpers that log context and raise consistent errors). Only where code can meaningfully respond. No wrapping code that can't fail.
8. **Type safety** — type annotations, replace `Any`/untyped code, runtime validation at API boundaries (Annotated types, Pydantic, Zod). Run type checker.

**Exhaustive** (all 18 checks) — thorough plus:

9. **Edge cases** — off-by-one, null/empty inputs, overflow, Unicode edge cases.
10. **Complexity** — flatten nested conditionals, reduce cyclomatic complexity.
11. **Deps** — remove verified-unused dependencies, flag vulnerable/outdated packages.
12. **Logging** — structured logging at entry points. No debug logging on hot paths.
13. **Concurrency** — race conditions, missing locks, async/await correctness.
14. **Accessibility** — semantic HTML, ARIA, keyboard nav, colour contrast (WCAG AA).
15. **API design** — consistent naming, HTTP methods, error formats, pagination.
16. **Cleanup AI slop** — removes AI-generated noise accumulated by earlier checks: redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests. Runs last (before test-validate) so it gets the final word.

Each check goes deep on one thing instead of shallow on everything.

### Fully file-based architecture

Every part of checkloop's behavior is defined in editable files at the project root — no Python changes needed to customize:

- **`checks/`** — one Markdown file per check. Each has YAML frontmatter (`id`, `label`) and a prompt body. Edit a prompt, add a new check, or remove one by modifying files.
- **`execution_plans/`** — TOML files that define which checks to run and which model for each. Three ship pre-populated (basic, thorough, exhaustive).
- **`prompt_templates/`** — boilerplate injected into every check at runtime: the scope prefix (review all code vs changed files) and commit message rules.

To add a new check, create a Markdown file in `checks/` and reference its ID in a plan TOML. To customize a prompt, edit the `.md` file directly.

### Per-check model selection

Not all checks have the same cognitive demands. A readability check is mostly pattern matching — rename this confusing variable, split this long function — and Sonnet handles it quickly and cleanly. But a security check needs to trace injection paths across a frontend router, a service layer, and a database query. A concurrency check needs to reason about race conditions spanning multiple threads and lock orderings. These require Opus's deeper multi-layer analysis.

Each plan file specifies which model to use for each check. The pre-populated plans route 14 of 18 checks to Sonnet and 4 to Opus:

- **Opus** for: `security`, `concurrency`, `perf`, `edge-cases` — checks where subtle issues span multiple code layers and require multi-step reasoning.
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

For codebases that already have accumulated AI slop, the `cleanup-ai-slop` check actively finds and removes it — redundant docstrings, unnecessary logging, misleading error handling, coverage-driven tests, and reverted operational config changes. It runs automatically as part of the exhaustive plan, or you can add it to any plan with `--plan thorough --checks cleanup-ai-slop`.

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

Run with `uv run checkloop` from the cloned directory, and pick a plan with `--plan`:

```bash
# Basic plan (default): readability, DRY, tests (all sonnet)
uv run checkloop --dir ~/my-project

# Thorough: adds security (opus), perf (opus), docs, errors, types
uv run checkloop --dir ~/my-project --plan thorough

# Exhaustive: all 18 checks with optimized model assignments, repeat twice
uv run checkloop --dir ~/my-project --plan exhaustive --cycles 2

# Or pick specific checks manually
uv run checkloop --dir ~/my-project --checks readability security tests

# Add a check on top of a plan
uv run checkloop --dir ~/my-project --plan thorough --checks cleanup-ai-slop

# Use your own plan file
uv run checkloop --dir ~/my-project --plan ./my-plan.toml

# Force all checks to opus for deeper analysis (slower)
uv run checkloop --dir ~/my-project --plan thorough --model opus

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

No. Similar approaches exist — LLMLOOP, SELF-REFINE, and various review-loop scripts. The idea of iterating on AI output isn't new. But `checkloop` is specifically designed for the "walk away and come back to better code" workflow: autonomous, multi-dimensional, with configurable review levels, convergence detection, and live progress streaming.

## Token usage (Be Careful!!!)

Each check is a full Claude Code session — reading files, making edits, running tests. A basic plan run (5 checks) on a medium-sized project typically uses 200K–500K tokens. Thorough (11 checks) or exhaustive (18 checks) with multiple cycles can easily reach several million tokens. Multi-cycle exhaustive runs on large codebases can burn through a significant portion of a daily API budget.

I often kick off runs right before bed or when stepping away from the keyboard. The tool is designed to run unattended, but can burn through a lot of tokens. Pay attention to your token useage.

## When to use it

I use it on feature branches before opening a PR. Point it at the branch, run two cycles with all checks, review the diff when it's done. It typically takes 20-40 minutes for a medium-sized project (a few thousand lines), and I consistently find that the resulting code is cleaner than what I'd produce with manual review alone.

It's not a replacement for human review. It's the first round that makes human review more productive.

The repo is at [github.com/alexander-marquardt/checkloop](https://github.com/alexander-marquardt/checkloop). MIT licensed.
