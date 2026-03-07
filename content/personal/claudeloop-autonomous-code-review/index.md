---
showtoc: true
title: "Autonomous Multi-Pass AI Code Review"
date: 2026-03-07
draft: false
slug: claudeloop-autonomous-code-review
tags: ["ai", "code-review", "developer-tooling", "claude"]
categories: ["AI-Assisted Development"]
description: "A simple Python tool that runs Claude Code in an autonomous loop."
---

Claude Code is genuinely good at code review — better than many humans at spotting certain categories of bugs. But I kept repeating the same pattern: I'd ask it to review a codebase, it would find real issues and fix them, and then I'd manually spot something obvious that it missed. This happens because a single pass through a codebase with the instruction "review everything" is fundamentally the wrong approach.

## The problem with "review everything"

When you ask an AI (or a human) to review code for everything at once — readability, security, test coverage, performance, error handling — each concern gets shallow attention. The model spreads itself thin. It catches the surface-level naming issues and maybe a missing null check, but it doesn't go deep on any single dimension.

Worse, some issues are invisible until you fix other issues first. A security vulnerability buried inside duplicated code across three files is nearly impossible to spot until you eliminate the duplication.

## Dimension-specific passes

The fix is simple: run multiple passes, each focused on a single concern.

There are seven built-in passes, each with a single focus:

1. **Readability** — rename confusing variables, split long functions, improve comments. No behaviour changes.
2. **DRY** — find repeated logic, extract shared helpers, consolidate constants.
3. **Tests** — write missing tests, target >=90% coverage, run the suite and fix failures.
4. **Documentation** — README, docstrings, config docs.
5. **Security** — injection vulnerabilities, hardcoded secrets, input validation, unsafe dependencies.
6. **Performance** — N+1 queries, blocking I/O, unnecessary allocations.
7. **Error handling** — try/except coverage, meaningful messages, logging.

Each pass goes deep on one thing instead of shallow on everything.

## Two loops, not one

The tool has two levels of iteration. The **inner loop** runs each review pass in sequence — readability, then DRY, then tests, then security, and so on. Each pass focuses on one dimension and builds on the cleanup of the previous one.

The **outer loop** (`--cycles`) repeats that entire sequence. Why? Because the first cycle's improvements create a new baseline. Code that was "clean enough" after cycle 1 now has new issues visible — the DRY pass extracted a helper, but cycle 2's readability pass notices the helper has a confusing name. Cycle 2's security pass catches a validation gap that only appeared after cycle 1's refactoring.

With `--cycles 2`, the tool runs all 7 passes, then runs all 7 again on the improved codebase. Each cycle finds a diminishing but real set of issues that the previous cycle's fixes made visible.

## Compounding improvements

Within a single cycle, the passes compound on each other:

1. The **readability** pass renames a variable from `d` to `user_document` and splits a 120-line function into four smaller ones.
2. The **DRY** pass now sees that two of those smaller functions are nearly identical and extracts a shared helper.
3. The **security** pass catches that the shared helper doesn't validate its input — an injection risk that was invisible when the logic was duplicated across 120 lines.
4. The **tests** pass writes tests against the now-clean API surface, achieving coverage that would have been painful to write against the original code.

Across cycles, the effect compounds further. The second cycle starts from a much cleaner codebase and consistently finds a second layer of issues that the first cycle couldn't see.

## The tool

I built [claudeloop](https://github.com/alexander-marquardt/claudeloop) — a ~300-line Python CLI that wraps Claude Code in an autonomous loop.

```bash
# Install
git clone https://github.com/alexander-marquardt/claudeloop.git
cd claudeloop && uv sync

# Run all 7 passes over your project, repeat twice
claudeloop --dir ~/my-project --all-passes --cycles 2
```

It streams progress in real time so you can see what Claude is reading, editing, and running:

```
[2m15s] [Read] src/api/handlers.py
[2m30s] [Edit] src/api/handlers.py
[3m01s] [Bash] $ pytest tests/ -x
[4m12s] [Write] tests/test_handlers.py
```

There's no hard timeout. It runs as long as Claude is producing output — only kills the process if it goes completely silent for 2 minutes (configurable with `--idle-timeout`).

The seven built-in passes cover: readability, DRY, tests, documentation, security, performance, and error handling. You can run any subset, and adding custom passes is just adding an entry to a Python list.

## Is this novel?

No. Similar approaches exist — LLMLOOP, SELF-REFINE, and various review-loop scripts. The idea of iterating on AI output isn't new. But `claudeloop` is specifically designed for the "walk away and come back to better code" workflow: autonomous, multi-dimensional, with sensible defaults and live progress streaming.

## When to use it

I use it on feature branches before opening a PR. Point it at the branch, run two cycles with all passes, review the diff when it's done. It typically takes 20-40 minutes for a medium-sized project (a few thousand lines), and I consistently find that the resulting code is cleaner than what I'd produce with manual review alone.

It's not a replacement for human review. It's the first pass that makes human review more productive.

The repo is at [github.com/alexander-marquardt/claudeloop](https://github.com/alexander-marquardt/claudeloop). MIT licensed.
