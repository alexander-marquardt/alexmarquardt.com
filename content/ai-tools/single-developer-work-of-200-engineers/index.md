---
showtoc: true
title: "How a Single Developer Can Do the Work of 200 Engineers"
date: 2026-11-08
draft: true
slug: single-developer-work-of-200-engineers
tags: ["ai", "agents", "developer-tooling", "claude", "engineering-productivity"]
categories: ["AI-Assisted Development"]
description: "The methodology behind one developer running a fleet of Claude Code agents: written rules, deterministic tests, CI gates, independent review and an agent control plane. With the measurements: three million lines of code, and as many merged pull requests a month as a 200-person open-source project."
---

## In short

I work alone on a project, with a fleet of AI coding agents doing the implementation. In October, its main repository merged 1,695 pull requests, about as many as Grafana, whose pull requests that month came from 198 people. Across the project's four repositories, the agents merge about 690 pull requests a week, where a typical engineer merges about two.

That is a large number, and it is not because I am unusually fast. It comes from a method: a set of rules, tests, gates and controls that let agents do the work of a large team without the codebase falling apart. This article shares that method, with the measurements behind it, how each was taken, and the objections they invite.

## What the code is

The project is a search interpretation layer for e-commerce, built on Elasticsearch. It reads what a shopper types, such as "blue trainers size 9 under $50", works out which words are a colour, a size, a price limit, a brand or a category, and turns them into a structured query: filters, category routing, boosts and synonyms, served in tiers from best match to related. Every decision it makes is explained in a debug payload, so a merchandiser can see why a product is where it is.

A second application, Studio, is where merchandisers edit the vocabularies and rules that drive it and inspect any search. It is demonstrated on a synthetic catalogue of about 380,000 SKUs across retail and industrial departments, produced by the data generator in one of the other repositories.

<!-- SCREENSHOT: a search with its tiers, applied filters and the debug panel open -->

## The numbers

### The size of the codebase

The main repository, measured at its current `main` (8 November 2026), in physical lines (blank lines and comments included):

| Part | Lines | Files |
|---|---|---|
| Backend product code (Python) | 401,000 | 651 |
| Frontend product code (TypeScript, TSX, CSS) | 216,000 | 767 |
| Backend tests (Python) | 1,627,000 | 3,819 |
| Frontend tests | 485,000 | 1,334 |
| Scripts and tooling (Python and shell) | 286,000 | 574 |
| **Code total** | **about 3.0 million** | |
| Documentation (Markdown) | 243,000 | 2,746 |
| Recorded test data (JSON, CSV) | 2,035,000 | 883 |

Three repositories sit beside it: a synthetic data generator (209,000 lines of code, 72,000 of them tests), a configuration and data repository (about a million lines, mostly data) and the agent-control repository described below (77,000 lines of code and tests).

Of the main repository's code, 70% is tests: 3.4 lines of test for every line of product code. That is deliberate, and it is the first half of how this works. More on that below.

### The rate of work

| Measure | Value |
|---|---|
| Merged pull requests, main repository, October 2026 | 1,695 (about 383 a week) |
| Merged pull requests, all four repositories, weeks 41–44 | about 690 a week |
| Merged pull requests, main repository, April to 8 November 2026 | about 6,400 |
| Lines added / deleted, main repository, October (excluding recorded data) | 1,189,000 / 348,000 |
| Median pull request size | about 420 changed lines |
| Issues filed / closed, main repository | 8,181 / 6,429 |
| Test functions, backend | 27,635 |
| Test cases, frontend | 12,467, plus 144 end-to-end spec files |
| CI | 58 workflows, 136 jobs |
| Merges later reverted | 0.2 to 0.7% |
| Commit authors | 1 person (3,023 of 3,039 commits on `main` since August; the other 16 are Dependabot) |

### How that compares with a well-known project

[Grafana](https://github.com/grafana/grafana) is one of the busiest open-source repositories on GitHub. Here is October 2026 for both, measured the same way from the GitHub API (merged pull requests; bots excluded from the author count):

| Repository | Merged PRs, October | People authoring them | Median PR size (changed lines) |
|---|---|---|---|
| grafana/grafana | 1,706 | 198 | 122 |
| My main repository | 1,695 | 1 | 492 |

The same number of merged pull requests as Grafana's 198 contributors, each four times larger, from one person. And that is one of my four repositories.

The author count includes occasional outside contributors, so Grafana's core team is smaller than 198. It is still a large, well-run engineering organisation, and the comparison is pull request for pull request.

### How that compares with published benchmarks

The comparison uses merged pull requests per engineer per week, because it is the most widely published productivity benchmark:

- [Graphite](https://graphite.dev/research) puts the median active developer at **2 merged PRs a week**.
- [LinearB's benchmarks](https://linearb.io/engineering-benchmarks/) put the elite tier at **above 2.25** merged PRs per developer per week.

| My output | Against the median (2/week) | Against the elite tier (2.25/week) |
|---|---|---|
| Main repository only, October (383/week) | 192 engineers | 170 engineers |
| All four repositories (690/week) | 345 engineers | 307 engineers |

The most conservative cell, main repository only against elite engineers, is 170.

And that comparison flatters the benchmark, not me. [Graphite's median pull request is 47 changed lines](https://graphite.dev/research/median-pr_size). Mine is about 420, nine times larger. If PR size were normalised, the numbers above would grow, not shrink.

Lines of code give a more extreme answer, which I do not lean on. The classic estimates for delivered code run from about 10 lines a day ([Brooks](https://blog.ndepend.com/mythical-man-month-10-lines-per-developer-day)) to 325–750 lines a month ([Capers Jones, as cited here](https://dzone.com/articles/programmer-productivity)). The main repository grew by 841,000 net lines of non-data code in October alone. Against Capers Jones, that is the monthly output of 1,100 to 2,600 programmers. Lines are a poor measure, and much of that is tests, so treat this as an upper bound that nobody should quote. The pull-request figures are the ones I stand behind.

## Fair objections

**"Pull requests are a vanity metric. Split the work finer and the count goes up."** True in general, which is why the PR size matters. These PRs are nine times the industry median, not smaller. The companion article on token use makes the same point from the other side: tokens per changed line, not per PR, is the honest efficiency figure.

**"Lines of code are meaningless."** Agreed. That is why the headline uses merged PRs, each of which passed review and CI, and the line counts are only there to show scale.

**"70% of it is tests. That's padding."** It is the opposite. Tests are what let one person trust code they did not type. Every test runs on recorded data in the repository, so it gives the same answer every time. Without that, the rate above would be a rate of producing bugs.

**"Then the quality must be bad."** 0.2 to 0.7% of merges are later reverted. Every PR is reviewed by a separate agent whose job is to find what is wrong with it, and must pass 136 CI jobs before it merges. The product is demonstrated live. The weak spot is rework, not breakage: about one fix round per merged PR, which I measure and am working to reduce.

**"An engineer does more than merge PRs: design, review, triage, operations."** So does this system. Review is done by agents. Triage is done by agents: 8,181 issues filed, each new one labelled with a severity, a product lane and an audience. Operations are done by agents: a watchdog checks the fleet every 15 minutes. What remains for me is the part that cannot be delegated: what the product should do, and judging whether it does it.

**"So you're saying engineers are obsolete."** No. I am saying the job has changed, from writing code to designing the system that writes, checks and merges it, and making the product decisions it cannot make. The rest of this article is what that system looks like.

## Why it does not fall apart

Give a dozen AI agents write access to a repository and the default outcome is chaos: duplicated helpers, tests that test nothing, documentation that describes code that no longer exists, fixes that silence a failure instead of curing it, and agents that wander off and rewrite things nobody asked them to touch. Every one of those happened here. Each one now has a rule, and each rule has a check that enforces it.

### 1. The rules are written down, and every rule has its incident

`CONTRIBUTING.md` is the contract every agent works under: 350 lines, pointing into 68 topic files (about 36,000 lines). It covers architecture boundaries, naming, error handling, testing, documentation and review.

Two things make it work rather than become a wall of text nobody reads:

- **Each rule cites the incident that produced it**, by issue number. An agent tempted to break a rule can read exactly what went wrong last time.
- **The file loaded into every agent call is capped in size.** The root guide that every agent reads on every model call is held to 2,133 bytes by a CI check. Everything else is a pointer. A guide that grows without limit gets skimmed; one that cannot grow stays read.

Decisions live in the repository, not in chat. When I rule on how something should behave, the ruling is quoted verbatim in the issue, with its date, and the work traces back to it. An agent never has to guess what I meant three weeks ago.

### 2. Deterministic tests, on recorded data

The rule is simple: **tests run on fixed data in the repository.** When a behaviour depends on a live system, the agent records the live response as a fixture and tests against that. No test reaches a shared cluster, so a test that passed yesterday passes today for the same code.

That is what makes 27,635 backend test functions and 12,467 frontend test cases an asset instead of a flaky-test tax. When a test fails, the code changed.

Tests are also held to account:

- A test module is named by what it pins (`test_facet_counts_are_floors.py`), and a script refuses a new one that is not.
- Documentation claims are tested against the code. A "claim test" compares a docs page with what the code does, and is proven to bite by planting false sentences and checking that it catches them.
- A flaky test is a severity-1 bug, not something to retry.

### 3. CI is the boss, and the gates are tested too

136 CI jobs run on every pull request. Some are ordinary (unit tests, type checks, end-to-end tests). Many exist because an agent once did something a human reviewer would have caught by instinct:

- **File-size caps.** No source file may grow past 1,750 lines without a stated exception. Agents love to keep appending to one file.
- **Audit greps.** About two dozen patterns, each tied to a failure class that slipped past review more than once, run on every diff.
- **Change obligations.** "If you touch X you also owe Y" is enforced by a script, not remembered.
- **An efficiency ratchet.** Efficiency readings may only improve. A daily run fails when one regresses past its baseline.
- **Process guards.** A process improvement ships with a deterministic check that fails when the improvement regresses.

The gates themselves get attacked. On one day, four separate reviews each found a new gate blind to a different spelling of the thing it was meant to catch (`./tests/` instead of `tests/`, a folded YAML value, a shell array). In one case 10 of 12 deliberately planted evasions got through. Since then, every new gate is run against a standard kit of evasions before review. An agent will find the gap in your gate. It is not malicious; it is optimising. The gate has to be built for that.

### 4. Every change is reviewed by an agent whose job is to say no

Every substantial change is reviewed twice against an adversarial review checklist: once by its author before opening the PR, and once by an independent reviewer agent before merging. The reviewer posts a verdict. Nothing merges without a verdict at the reviewed commit and green CI.

Review agents are separate from implementing agents, with their own instructions and a narrower set of tools. The author's confidence carries no weight.

### 5. A control plane for the agents, under version control

The agents themselves are run by code, not by me typing prompts. That code lives in its own repository, separate from the product, so process changes never tangle with product changes:

- **An allocator** runs the agent slots on a cloud VM from a single queue. Work is drawn by priority and by weighted lanes (product areas, CI throughput, reviews of old PRs). Urgent work goes to the front of the queue, never around it.
- **A watchdog** runs every 15 minutes with no AI involved. It checks for stalls, red CI on `main`, PRs that have stopped moving, and jobs that failed.
- **An oversight loop** checks the watchdog: each run records whether something was caught by a trigger, found clean, or missed. A miss files its own fix.
- **Stop the line.** A red `main` or a stuck PR is fixed before new work starts, on a clock. This is the Toyota rule, and it matters more with agents than with people, because agents will happily build on top of a broken base.
- **Protected checkouts.** The checkout I demo from is never written to by an agent. Every agent works in its own clone, and the hooks refuse writes outside it.

The control plane has been redesigned twice, the second time from scratch. The first two versions grew by patching: a watcher here, a re-send there. When it became clear that patches were adding failure modes faster than they removed them, I stopped patching and had it redesigned as a minimal allocator over one table. That is the rule now: a stall gets fixed today and gets a deterministic rule with a test, so it cannot recur.

### 6. Issues are written so an agent can finish them

Every issue title says what should happen and what happens now: "X should do Y; currently it does Z." The body states the consequence, the trigger, who is affected, and a "Done when" list that traces back to the request it came from. An agent picks up an issue cold, with no conversation history, and knows when it is finished.

### 7. What I actually do

I decide what the product should do. I test it the way a customer would, and when something is wrong I say so in plain words, often with a screenshot. Those words become an issue with my sentence quoted in it. I make the rulings that the rules cannot: when two good designs conflict, which one wins.

I also design the system described above, and every time it fails, I change it so that failure cannot happen again. That is the job now. It is closer to running an engineering organisation than to being an engineer in one, except that the organisation is software and it does not go home at night.

## What it costs, and what still breaks

None of this is free. A fleet of agents running around the clock uses a lot of tokens, and at the start a full weekly allowance lasted about a day. Getting that under control was a project of its own, and the [next article](/ai-tools/agent-fleet-token-efficiency/) covers it: how I measured where the tokens went and cut tokens per line of code to under a third.

What still breaks: rework. About one fix round per merged PR is too many, and it is where the next round of improvements goes. Agents still occasionally solve the wrong problem confidently, which is why the rulings are quoted and the reviews are adversarial.

## Why this should matter to anyone running engineering

The bottleneck is no longer typing code. It is specifying what should be built, checking that it was built correctly, and keeping a codebase coherent while it changes at hundreds of pull requests a week. Teams that treat AI as autocomplete for individual engineers will get a modest speed-up. The step change comes from building the system around the agents: written rules with their reasons, deterministic tests, CI that enforces what reviewers used to remember, independent review, and a control plane that runs the fleet.

None of the pieces is exotic. Each one is something a good engineering team already knows it should do, applied without exception because agents, unlike people, will not fill the gaps with judgement. With them in place, one developer did on this project what used to take a large team, and the numbers above show how that was measured.
