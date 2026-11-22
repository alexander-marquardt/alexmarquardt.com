---
showtoc: true
title: "Running tens of coding agents on one codebase: the orchestration layer, what each part does and why it exists"
date: 2026-11-22
draft: true
slug: coding-agent-fleet-orchestration-layer
tags: ["ai", "agents", "developer-tooling", "claude", "engineering-productivity"]
categories: ["AI-Assisted Development"]
description: "The machinery that lets sixteen coding agents work on the same repositories at once: a deterministic allocator, weighted lanes, hot-file splits, an optimistic merge train and CI run as a capacity problem. Each part is described as the failure it answers, how it works and what it measurably changed."
---

Two earlier articles covered [the guardrails that keep a codebase sound at 1,600 merged PRs a month](/ai-tools/coding-agents-codebase-under-control/) and [how the same work came to cost a third of the tokens](/ai-tools/agent-fleet-token-efficiency/). Neither covered the machinery that lets ten or more agents work on the same repositories at once without trampling each other. That machinery is the subject of this article.

Almost every part of it exists because a specific failure happened at scale. Each failure is one any team will hit once its parallel workers outnumber the files they share, whether the workers are agents or people. So each section below is laid out the same way: the problem, the mechanism that answers it, and one number from the fleet's own records showing what it changed. Where the number is bad, it is reported as it is.

Deadlocks, where work waits on other work and nothing moves, get [an article of their own](https://github.com/alexander-marquardt/alexmarquardt.com/issues/28), so they are only mentioned here.

## 1. The shape of the system

**The problem.** Agents left to choose their own next task pick whatever was asked for last, work on the same file at the same moment, and spend tokens deciding what to do before doing anything. A session that "manages" other agents is still a model reading its whole context on every decision.

**The mechanism.** One allocator, called v3, hands out a fixed number of slots: 12 work slots and 4 review slots, across 7 repositories. It is a plain Python loop that runs every 60 seconds over one SQLite table of jobs. Each tick it:

- ends the jobs whose processes have exited, reading the result file each agent writes;
- picks new work by fixed rules (section 2);
- starts an agent for each free slot.

Every agent works in a throwaway clone of its repository, never in a shared checkout, and hands its change back as a file the allocator turns into a commit, a push and a pull request. A coordinator session reviews what the allocator cannot decide. The allocator also heals itself: a stalled job is stopped and rethought instead of being left to time out (section 7, in the next draft).

Why a deterministic allocator rather than an agent deciding what to do next? Cost and repeatability. A rule in code makes the same choice from the same state every time. It can be tested on fixed data, and it spends nothing.

**The number.** In the seven days to 22 November the allocator started **6,946 agent jobs** across the 7 repositories. They break down as:

| Job kind | Started |
|---|---|
| Reviews | 1,857 |
| Implementations | 1,640 |
| Fix rounds | 1,246 |
| Rebases | 813 |
| Rethinks | 611 |
| Triages | 402 |

Behind them were 836 dispatch decisions, and not one of those decisions spent a model token.

## 2. What to work on: lanes, weights and a priority number

**The problem.** A single queue ordered by "most important first" lets features crowd out everything else: CI speed, security, cleanup and the articles about the work. Each of these always looks less urgent than the next feature, until it is the reason nothing merges.

**The mechanism.** Every issue belongs to one lane, and each lane has a weight that sets its share of the new work the allocator picks. A few classes that cut across lanes (bugs, and issues that have stalled) carry weights too. The rule for which issue takes a free slot has three steps:

1. Draw a lane by weight.
2. Within that lane, take the highest priority number.
3. On a tie, take the newest issue.

Urgent work, a red main and a few other rules go ahead of the draw, never around it.

The trade-off is built in. Everything that goes ahead of the draw is capacity the weights never see. When many issues carry the top number, the weights stop steering.

**The number.** Over the seven days, **311 of the 836 dispatches (37%) went ahead of the lane draw**: 268 were urgent, 24 were critical and 19 were demo work. The weights shared out the other 525. Here is how the draw's picks compared with each weight's target:

| Lane or class | Weight | Target share | Measured share (7 days) |
|---|---|---|---|
| The orchestrator itself | 50 | 14.8% | 0.8% |
| The server library | 40 | 11.9% | 8.0% |
| Security | 30 | 8.9% | 3.2% |
| Integrator experience | 25 | 7.4% | 9.3% |
| Runtime performance | 25 | 7.4% | 6.9% |
| Bugs (a class) | 20 | 5.9% | 25.7% |
| Data generation | 20 | 5.9% | 8.4% |
| Developer efficiency | 20 | 5.9% | 7.4% |
| CI throughput | 15 | 4.5% | 7.2% |
| Code cleanliness | 15 | 4.5% | 4.8% |
| Benchmarks and articles | 10 | 3.0% | 3.8% |

Most lanes land within a few points of their target. The three that do not show what the weights cannot do:

- **The orchestrator's own lane** got 0.8% of a 14.8% share. For most of the week its changes were made from a separate machine, outside the draw, so its issues were held.
- **Security** had fewer ready issues than its weight could use. A weight steers only the work that is ready to pick.
- **The bug class** took four times its share.

A weight is a target, not a guarantee. The allocator therefore prints the lanes under half their share every hour, and gives the reason for each ready issue it did not pick.

## 3. Merge conflicts at fleet scale

**The problem.** At this rate of change a few files are edited by nearly every PR: the allocator's main loop, its command-line entry point, the index of a docs folder. Every PR that touches one conflicts with every other PR that touched it and merged first. Each conflict costs a rebase job, a fresh CI run and often another review, and the rebased PR can conflict again before it merges.

**The mechanism.** Four parts, from finding the problem to preventing it:

- **The hot-file finder.** Every 30 minutes it counts the files that conflicted on 3 or more PRs within 7 days. For each, it files one split issue, the file with the most PRs first, at most two a day per repository.
- **Split by owner, as a move-only change.** The split moves each family of functions into its own module, and each module has one owner, so two PRs on different families touch different files. The split changes no behaviour, and a check that compares the syntax trees before and after proves it moved code without changing it.
- **Shared lines.** Some lines are edited by every PR, such as one long import line or a list in an index file. They become one entry per line, a generated file, or a file git merges as a union.
- **File leases.** An agent is refused an edit to a file that another live agent or an open PR holds. It has to wait for the other work to finish, or work around that file.

**The number.** Since 17 November the finder has filed **21 split issues across 4 repositories**. The worst file was the allocator's own main loop: **57 PRs conflicted on it, 37 of them in the 7 days before its split issue was filed**. The command-line entry point came next, at 45. The first splits to merge were two modules in the data generator. The larger one had conflicted on 7 PRs in the week before its split, and on **none in the four days since**; the other went from 4 to none.

The loop's own split merged on 22 November, too recently to give a before-and-after number yet.

## 4. Merging without a person: optimistic merging and the merge train

**The problem.** A merge queue that tests each PR on top of the one ahead of it is safe, but it is serial. At hundreds of merges a week it becomes the bottleneck, and one slow or flaky PR holds up everything behind it. Waiting for a person to press merge is slower still.

**The mechanism.** Merge on green, catch a red main fast, and deploy only commits that passed:

- A PR whose own CI is green merges without first being re-tested on the newest main.
- When main goes red, the cause gets the front of the queue: a fix job, its review, the CI runners, and the merge queue. PRs that cannot merge into the red main are not tested against it.
- If no fix has merged 90 minutes after main went red, the commit that broke it is reverted.
- Deploys read only commits whose CI passed, so a red main is never what runs.

The bet is that catching and fixing a rare red main costs less than testing every PR in series. The criterion for that bet is strict: 30 merges in a row in which every red main was back to green within 45 minutes, with no red commit deployed.

**The number.** The criterion is **not met yet**. In the week from 15 November, main went red **36 times across the repositories, and 11 of those spells (31%) were green again within 45 minutes**. The median spell lasted 107 minutes. Since 1 November it is 14 of 102 spells, with a median of 112 minutes.

Most of the time goes before the fix starts, not into the fix itself: finding which commit broke main, and getting a slot and a runner for its fix. That is where the next changes are aimed.

## 5. CI as a capacity problem

**The problem.** Sixteen agents can push faster than CI can test. Once that happens, CI is no longer a check you run. It is a shared resource with a queue, and it needs the same treatment as the agent slots: a known capacity, a measured wait, and limits so that one job cannot take it all.

**The mechanism.**

- **Self-hosted runners on Spot machines.** A Spot machine is a spare cloud VM that costs a fraction of the usual price but can be taken back at any moment. A watchdog starts the machine when jobs are queued. When Spot has no capacity for 10 minutes, it walks a chain of fallbacks: another machine type, then a standard (non-Spot) machine. It stops the machine after 30 minutes with no job queued.
- **Stale registrations.** A runner registration that has outlived its machine is cleaned up, so no job waits on a runner that no longer exists.
- **A memory guard.** It stops a test run before the machine runs out of memory. It is better to lose one run than the whole runner.
- **Step budgets.** Each CI step has a time budget, so a slow step is visible as a slow step and does not just lengthen the run.
- **A timed-out job is rerun once.** A timeout is not a failing test, so it is not sent to a fix round. Only a second timeout on the same commit is.

**The number.** On 22 November, across 258 jobs from 60 runs on the data generator's self-hosted runners, **the median job waited 1.8 minutes for a runner, and one in ten waited 14.5 minutes or more** (the longest was 23.9). The machine stops after 30 idle minutes, so the first job after a quiet spell waits for it to boot. For comparison, the main repository's jobs on GitHub-hosted runners waited a median of 1.3 minutes, and at most 3.1 minutes, over 57 jobs that evening.

<!--
DRAFT NOTES (slice 1 of 2, alexander-marquardt/alexmarquardt.com#35). Not rendered: the page is draft: true.

Slice 2 adds sections 6 to 10, each with one measured number:
6. After CI: triage, not a reflex fix: the share of red PR runs that were a flake, a timeout or a mechanical failure,
   and the fix rounds held until the cause changed.
7. Self-healing, the three whys: the caught-and-missed tally over time.
8. Changing the orchestrator itself: the precheck, the post-deploy self-check and rollback, the drills, the handback
   criteria; the number of rollbacks.
9. Context between agent calls: the handover pack's before-and-after table on re-reading, reported whatever it shows.
10. What carries over to a human team, and what is specific to agents.

Before publishing:
- Replace the deadlock link (issue #28) with the published article's URL.
- Section 2: say why the bug class took 25.7% against a 5.9% target. Check how the draw treats a lane with nothing
  ready before writing a cause.
- Section 3: re-measure the main loop's conflicts a week after its split merged (22 November). Confirm the syntax-tree
  check and the lease refusals by name, and give a count of refusals if the leases record one.
- Section 4: re-measure the red-main spells; publish the 30-merge ledger once it has a run of 30.
- Section 5: add runner occupancy over 24 hours once the census keeps a time series (today it keeps only the
  current reading).

Sources: the allocator's job table and allocation log (sections 1 and 2), its conflict and hot-split tables
(section 3), its red-spell table (section 4), the GitHub Actions jobs API (section 5). Every figure counted from
2026-11-15T20:00Z to 2026-11-22T20:00Z unless the text gives another window.
-->
