---
showtoc: true
title: "Make the System Remember: Running a Fleet of Coding Agents at 7.5x Less per Merged PR"
date: 2026-11-07
draft: true
slug: agent-fleet-token-efficiency
tags: ["ai", "agents", "developer-tooling", "claude", "token-efficiency"]
categories: ["AI-Assisted Development"]
description: "What ten weeks of measurement taught us about the token cost of running many AI coding agents in parallel on a large codebase: where the tokens actually went, what we changed, and what it did and did not buy."
---

For the last two months, most of the code on one of my projects has been written by AI agents. One coordinating session hands out work. Up to a dozen background agents each take one issue, write the change and its tests, and open a pull request. A separate, adversarial review agent has to approve every PR before it can merge.

It works. But in the first weeks it was expensive in a way that was hard to reason about. A full weekly token allowance lasted about a day with four agents running. Our guesses about why were mostly wrong.

This article covers the ten weeks from the end of August to early November:
- how we measured where the tokens went;
- what we changed;
- what the numbers say now, including the parts that did not improve.

The short version: the cost per merged PR fell from about $72 to about $9.50, 7.5 times less. The fleet now merges about 4.5 times as many PRs a week while spending 40% less. Almost all of that came from one idea: **don't make the model remember; make the system remember.**

## The setup

The codebase is a multi-service search product, mostly Python and TypeScript. It has about 2,300 source files and a CI pipeline of about 140 jobs. Alongside it sit three smaller repositories that the agents also work in: a data generator, and two demo configurations.

The process looks like this:

- **A coordinator session** watches the queue, CI and the open PRs. It doesn't write code.
- **Agents** run on a single cloud VM. Each one gets one task, its own clone of the repository, and a short written brief.
- **An allocator** decides what runs next. It started as instructions to the coordinator. It is now a small program: a queue, weighted by area, with slots per kind of work.
- **Every PR is reviewed by a different agent**, which is told to find reasons not to merge. A PR merges only with an approving verdict at its current head and green CI, through a merge queue.

At peak this produces the PR flow of a large engineering team: 600 to 870 merged PRs a week across the four repositories. Each PR is one scoped issue, with its tests, docs and changelog entry.

## Measure first

The first thing we did was stop guessing. Every agent session writes a transcript, and every model request in it records its token usage. That usage is split into fresh input, cache writes, cache reads and output. A script over those transcripts, with no model calls, prices each request at list API prices. The result is a comparable unit, not the bill.

Two things about the method matter more than they look:

1. **Count each request once.** One request appears in a transcript as several records, one per content block. Our first daily cost script counted each record, and its daily figure was about a third too high. Check the meter before you trust the savings.
2. **Divide by work done, not time.** Tokens per hour is a budget signal. Tokens per merged PR is the efficiency signal. On the first day after our biggest change, hourly spend did not move at all, while merged PRs per hour went from 0.57 to 2.06. The saving went into throughput.

The first breakdown was full of surprises:

- **The agent's brief was 0.6% of cost.** We had spent days shortening briefs.
- **File reads were about 27%**, a long tail with no single hotspot.
- **The agents' own output was about 26%.**
- **The system prompt and tool definitions were about 15%.**
- An outside estimate of file-read cost turned out to be off by 5x because of a parsing bug.

The model that explains all of it is simple. Every request re-reads the whole conversation so far. **Cost is roughly the number of requests times the context carried.** An agent at 300k tokens of context costs about three times as much per call as one at 100k, for every remaining call it makes.

The most counter-intuitive measurement came next. We measured how much of the carried context was ever used again. Almost all of it was: only 1.5 to 3% was never referenced again. The waste wasn't irrelevant content. It was *relevant* content carried across hundreds of requests. Re-reading a file once when it is needed costs about 1.25 times its size. Carrying it costs 0.1 times its size on every request. After about a dozen requests, carrying loses.

## What we changed

### Short-lived agents with short handoffs

The biggest change came first: one agent, one task, then it ends.

When an agent's work is unfinished, it doesn't keep going in a growing conversation. Its state goes to durable places:
- the code to a pushed branch;
- the plan to a short status comment on the PR, with the exact next steps, links and the head commit.

A fresh agent starts from that. Its handoff is under 30 lines.

A hook enforces this rather than an instruction. It watches each agent's context size. At a soft threshold, the agent is told to hand off at its next commit. At a hard threshold, only state-saving commands still run: commit, push, and post a status comment.

On the first day, the median context per agent request fell from 218k to 101k tokens. It fell within every kind of agent: implementation went from 331k to 143k, review from 149k to 90k. The share of agents that ever went past 150k fell from 73% to 25%.

This beats in-context compression because the summary is deliberate, short and auditable. It survives crashes, usage limits and account switches. A human or another agent can read it. A fresh agent pays its orientation cost once, typically tens of thousands of tokens, and earns it back within a few calls.

### Keep the prompt cache warm

A later audit found the next-largest cost. When an agent waited more than five minutes, for CI, a long test or a polling loop, its prompt cache expired. The next call then re-sent the whole context at the cache-write price. That happened about 800 times a day, and it was **about 31% of all agent spend**.

The fix was mechanical. Wait helpers return before 270 seconds, and a guard refuses longer foreground waits. Cache expiry fell to 0.7% of spend.

One more finding from the same experiments: polling is not the waste it looks like. A poll inside the cache lifetime keeps the cache warm, and a cold restart costs about ten times a poll. The real lever is taking long waits out of an agent's life altogether.

### Stop loading what most agents don't need

Every agent's first message carried about 10k tokens of shared context: project instructions, plus an always-loaded memory index that had grown to about 90 lines. Most of those lines were orchestration rules only the coordinator needed.

Worse, that shared context sat after the last cache breakpoint, in the same block as each agent's own task prompt. A one-word difference in the task missed the cache for the whole block. Across 1,411 agents in one day, the median first turn read 3.2k tokens from cache and wrote 11k fresh.

The index now holds 8 universal lines, and the rest moved into secondary indexes that an agent opens when its task needs them. The first-turn cache write fell from about 11.2k to about 4.5k tokens.

The lesson: anything injected into every agent belongs before the cache breakpoint, or nowhere.

### Smaller changes that added up

- **Reports on a state change only**, never "still waiting".
- **Targeted tests instead of full suites**, with one host-wide lock for heavy jobs.
- **No language-model review of a mechanical change.** A rebase, a regenerated file or a pure merge of main gets a mechanical check. The approving verdict carries over when the merged tree is identical.
- **Links to a specific comment** instead of "read the thread".
- **One call for a batch of edits** across several files, instead of one turn per edit. Each turn re-reads the whole conversation.
- **Model routing**, decided by whether a gate can catch a task's failure mode. Covered below.

## Deterministic over checklists

This is the part I would most like other teams to take away.

In the first weeks, every incident produced a new rule in a prompt. The prompts grew, and the rules were followed most of the time. "Most of the time", across hundreds of agents a day, means several failures a day. It also means every agent pays to read every rule.

So we changed the rule about rules. **Every rule becomes a gate, a test or a refusal in the tooling, not prose for the model to remember.** Some examples:

- A PR cannot merge without an approving verdict *at its current head*. The merge tooling checks this, and the reviewer is not trusted to say so.
- An agent cannot write into the main checkout. The tool call is refused.
- A catalog of every check is generated from the code, so nobody has to know where the checks are.
- Fire drills prove that the gates still bite.

I used a hospital analogy for this idea in an [earlier article on query execution](https://www.elastic.co/search-labs/blog/agentic-ai-search-deterministic-guardrail-query-execution). There, the model proposes a query, and deterministic code decides what actually executes. The same idea turns out to govern how the software gets built:

- **The patient chart is the state.** No doctor is expected to remember every patient; whoever is on shift reads the chart. Our status comments and issue threads are the chart, and each agent is the clinician on shift.
- **Shift handover is the 30-line handoff.** Wards use a short, structured handover, not a replay of the whole day. A fresh agent with a structured handoff beats a tired agent with a huge memory.
- **Barcode scanning is the gate.** Hospitals stopped relying on the nurse remembering to check the wristband against the prescription; the scanner refuses the wrong drug. Our gates refuse the wrong merge.

Taken together, this is what made the context reduction possible. A smaller context only saves money if nothing important lived in it. Once state lives in files and on GitHub, rules live in code, and knowledge lives in generated docs read on demand, the model can forget almost everything. The work barely notices.

## The results

These figures come from one script over every transcript on both hosts, about 1.36 million model requests. Each is priced at list prices.

The script was checked against a baseline recorded at the start, for the same weeks: $23.1k against $22.6k, within 2.3%. Merged PRs count all four repositories. Weeks are ISO weeks, and the last one is partial.

| Week | Merged PRs | Fleet cost | Cost per merged PR | Median PR size (lines) |
|---|---|---|---|---|
| W36 | 195 | $12.4k | $63.7 | 915 |
| W37 | 153 | $10.8k | $70.5 | 998 |
| W38 | 113 | $8.6k | $76.0 | 1,132 |
| W39 | 151 | $12.1k | $80.5 | 1,078 |
| W40 (work starts) | 196 | $7.9k | $40.2 | 1,132 |
| W41 | 632 | $6.2k | $9.8 | 489 |
| W42 | 871 | $8.6k | $9.9 | 467 |
| W43 | 587 | $6.0k | $10.2 | 347 |
| W44 | 670 | $6.2k | $9.2 | 394 |
| W45 (partial) | 641 | $5.4k | $8.4 | 409 |

**Before** (W36–W39): $71.8 per merged PR, about 150 PRs and $11k a week.

**After** (W41–W45): $9.5 per merged PR, about 680 PRs and $6.5k a week.

That is **7.5 times less per merged PR**, and 4.5 times more merged work for 40% less spend.

PRs also got about 2.5 times smaller, from a median of about 1,030 changed lines to about 410. One task per agent produces smaller PRs, and smaller PRs are easier to review. **Per line of change, the gain is about 3x.** That is the more conservative number, and the one I would quote.

The coordinator's share of total spend fell from 13% to 6%.

### Almost all of it came in one step

Cost per merged PR fell from W40 to W41 and has been flat at $8–10 since. That step was the move to short-lived agents with short handoffs and a context ceiling. The later fixes were real; the cache-lifetime fix alone took 31% of agent spend down to under 1%. But they held the cost per PR flat while other things pushed it up:

- **Model choice.** We first routed routine work to a smaller model, which took it to 63% of spend by W42. Later we moved standard implementation back to the strongest model for quality. By W45 that model was 81% of spend. That trade was deliberate, and it is part of why the cost per PR did not keep falling.
- **Harder work.** As the easy issues ran out, the remaining ones were larger and touched more of the system.

Since W41, the rewrites of the orchestration bought reliability and volume, not a lower cost per PR. These were a queue-driven allocator, and one VM for all agents. The next lever is the implementation job itself, now about 80% of agent spend. A review round costs about $0.24 and a fix round about $0.54.

## Quality, measured alongside cost

A cost win can hide a quality loss, so we tracked both:

- **Reverts** went from 0–1 a week to 2–4 a week in W42–W44. That is 0.3–0.7% of merges, at four times the volume. W45 has had none so far.
- **Review verdicts per merged PR** went from 1.77 to about 1.6.
- **Fix rounds per merged PR went up**, from 0.80 to between 0.9 and 1.0. A weekly report puts rework at about 20% of agent tokens.

So the cost per PR fell, and the churn per PR did not. That is the most useful number in this article for anyone planning their own setup. The next round of work is on getting a change right the first time, not on making each attempt cheaper.

## What didn't work

- **Shortening the brief.** At 0.6% of cost, it was never the problem.
- **A blind cap on tool output.** Cutting long command output to its head and tail removed text the agent later needed about half the time. Per-command digests are the version worth building, such as only the failing tests or only the tail of a gate run.
- **Fewer review rounds as a goal in itself.** 71% of blocking review findings were mechanical: CI is red, a change has no test, the docs drifted, the branch is behind main. A mechanical gate before review saves about 3%. Skipping a re-review after a pure merge of main saves under 1.5%, because most re-reviews follow a real fix.
- **Intuition.** A cheap read-only audit of the real transcripts, run by a strong model, found the 31% cache lever that weeks of tuning had missed.

## When this pays off

All of this pays off most with many agents on a large, rule-heavy repository, where the same context is carried across thousands of requests a day. For a single developer with one session, the per-request arithmetic is the same, but the absolute numbers are small. Most of the gate machinery would be overhead.

Volume brings its own problem: at team-sized PR volume, the bottleneck moves from writing code to *landing* it. A merge queue tests PRs in groups against the latest main, and one failing PR drops its whole group. That deserves its own article.

## Takeaways

1. **Measure from the transcripts, per unit of work.** Count each request once, price it, and divide by merged PRs, not hours.
2. **Cost is requests times context.** Find out what your agents carry and for how long, before cutting anything.
3. **Hand off instead of compressing.** One task per agent, state in durable places, a hard context ceiling enforced by a hook.
4. **Keep the prompt cache warm**, and put shared context before the cache breakpoint.
5. **Turn every rule into a gate.** That is what lets the model forget.
6. **Measure quality next to cost**, and say when it didn't improve.
