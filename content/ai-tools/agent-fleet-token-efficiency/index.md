---
showtoc: true
title: "My Coding Agents Burned a Week of Tokens in a Day. Here's How I Got 5.5x More Work out of Each Token"
date: 2026-11-07
draft: true
slug: agent-fleet-token-efficiency
tags: ["ai", "agents", "developer-tooling", "claude", "token-efficiency"]
categories: ["AI-Assisted Development"]
description: "If your AI coding agents burn through tokens too fast: why context size drives the cost, how to measure it from the transcripts already on your disk, and what cut tokens per merged PR 5.5x across a fleet of agents, including what didn't work."
---

## Summary

AI coding agents use tokens fast. I have a project with a significant amount of code written by AI agents, and with four agents running, a full weekly token allowance lasted about a day. This article reports what drives that cost, how to measure it, and which changes reduced it, with the measured effect of each, including the ones that had none.

Measured from the agents' own transcripts (about 1.36 million model requests over ten weeks):

- **Tokens per merged PR fell 5.5x**, from about 118 million to about 21 million.
- **Per changed line, they fell 3.3x**, from about 85,000 to about 26,000.
- **The fleet merges 4.4 times as many PRs a week, on 19% fewer tokens.**
- **The system became more reliable at the same time**, because most of what made it expensive was also what made it fragile.

The common principle: **don't make the model remember; make the system remember.**

### The findings in brief

Everything below follows from one fact: the model has no memory, so every call re-reads the whole conversation, and tokens are roughly the number of calls times the context carried. The rest of the article gives the evidence for each finding.

1. **Measure from the transcripts, per unit of work.** They're already on your disk. Count each request once, and divide by merged PRs, not by hours.
2. **Hand off instead of compressing.** One task per agent, a handoff under 30 lines, and a context ceiling enforced by a hook. This one change produced most of the 5.5x.
3. **Keep the prompt cache warm, and load less into every agent.** Cache expiry was 31% of agent usage. It's now 0.7%.
4. **Don't hand an agent a checklist; write the code.** A rule that can be checked deterministically becomes a gate. That's what lets the model forget.
5. **Let a program take load off the AI.** Moving routine work into a program cut the coordinating session's tokens per merged PR by about two thirds, and the overnight gaps in checking stopped.
6. **Make the codebase easy for a new developer.** Code maps, short comments with pointers and small modules help agents for the same reason they help people. An agent is a new developer every time it starts.
7. **Measure quality next to tokens.** Tokens per PR fell; rework per PR didn't.

The arithmetic is the same for one session as for a dozen agents, so most of this applies without a fleet. A short section near the end covers the single-session case.

## The setup

One coordinating session hands out work. Up to a dozen background agents each take one issue, write the change and its tests, and open a pull request. A separate review agent, told to look for reasons *not* to merge, has to approve every PR before it lands.

The codebase is a multi-service search product, mostly Python and TypeScript, with about 2,300 source files and a CI pipeline of about 140 jobs. Alongside it sit three smaller repositories the agents also work in: a data generator and two demo configurations.

- **The coordinator session** watches the queue, CI and the open PRs. It doesn't write code.
- **Agents** run on a single cloud VM. Each one gets one task, its own clone of the repository, and a short written brief.
- **A program decides what runs next**: a queue, weighted by area, with a fixed number of slots per kind of work.
- **Every PR is reviewed by a different agent.** A PR merges only with an approving verdict at its current head and green CI, through a merge queue.

The fleet merges 600 to 870 PRs a week across the four repositories, the PR flow of a large engineering team. Each PR is one scoped issue, with its tests, docs and changelog entry.

## Why agents burn through tokens

The cost follows from how an agent talks to the model, which isn't how most people picture it.

A language model has no memory between calls. Each time the agent calls it, the whole conversation is sent again: the system prompt, the tool definitions, every message, every file the agent has read and every command output it has seen. The model reads all of that, then writes its answer one token at a time, and each new token is produced by running the model over everything before it, including the tokens it has just written. That's what "autoregressive" means, and [The Illustrated GPT-2](https://jalammar.github.io/illustrated-gpt2/) is a good visual explanation of it.

An agent works in a loop on top of that. The model asks for a tool (read this file, run these tests), the tool's output is appended to the conversation, and the whole conversation goes back to the model for the next step. So an agent that makes 200 tool calls sends its conversation 200 times, and the conversation gets longer every time.

A rough illustration: an agent that starts at 20k tokens and grows to 150k carries about 85k on an average call. Over 200 calls, that's about 17 million tokens processed, even though the final conversation is only 150k long. Double the calls, or double the average context, and you double the total.

**Tokens used are roughly the number of calls times the context carried.** An agent at 300k tokens of context reads three times as many tokens per call as one at 100k, on every call it makes until it finishes.

### Where the cache comes in

Consecutive calls share almost all of their content: call 101 is call 100 plus one more tool result. So the provider can keep the already-processed start of the conversation for a short while, which is [prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching). Re-sending a cached prefix is billed at about a tenth of the normal input price. Writing a new prefix into the cache costs 1.25 times the normal price (or twice the price for a one-hour cache). The default cache lives for five minutes, and every use resets the clock.

Three consequences shaped everything that follows:

- **Cache reads dominate the token count.** They're 95 to 98% of all tokens in this fleet, because every call re-reads the conversation so far, and almost all of it comes from the cache.
- **Cheap per token isn't cheap in total.** Even at a tenth of the price, cache reads were 48 to 60% of the weighted cost in my measurements. Carrying context is the bill.
- **A cache miss is expensive.** If an agent sits idle for more than five minutes, its cache expires, and the next call pays the write price for the *entire* conversation, not just the new part.

So there are really only two levers: fewer calls, and less context per call. The brief and the output are small by comparison. Almost every change in this article pulls one of those two levers, which is why I focused on context size rather than on making prompts shorter.

## The results

These figures come from one script over every transcript on both hosts, about 1.36 million model requests. Every token counts once: fresh input, cache writes, cache reads and output.

The script was checked against a baseline recorded at the start, for the same weeks, and agreed within 2.3%. Merged PRs count all four repositories. Weeks are ISO weeks, and the last one is partial.

Changed lines are additions plus deletions. A few PRs a week regenerate data files or fixtures and change tens of thousands of lines each, so for tokens per line, a PR counts at most 5,000 lines.

| Week | Merged PRs | Tokens | Tokens per merged PR | Median PR size (lines) | Tokens per changed line |
|---|---|---|---|---|---|
| W36 | 195 | 19.6B | 101M | 915 | 84k |
| W37 | 153 | 16.3B | 106M | 998 | 82k |
| W38 | 113 | 12.9B | 114M | 1,132 | 72k |
| W39 | 151 | 23.3B | 154M | 1,078 | 97k |
| W40 (work starts) | 196 | 20.7B | 106M | 1,132 | 58k |
| W41 | 632 | 12.2B | 19M | 489 | 21k |
| W42 | 871 | 24.4B | 28M | 467 | 31k |
| W43 | 587 | 12.4B | 21M | 347 | 33k |
| W44 | 670 | 11.9B | 18M | 394 | 21k |
| W45 (partial) | 641 | 11.9B | 19M | 411 | 23k |

**Before** (W36–W39): 118M tokens per merged PR and 85k per changed line, at about 150 PRs and 18 billion tokens a week.

**After** (W41–W45): 21M tokens per merged PR and 26k per changed line, at about 680 PRs and 15 billion tokens a week.

That's **5.5 times fewer tokens per merged PR**, and 4.4 times more merged work on 19% fewer tokens a week.

PRs also got about 2.4 times smaller, from a median of about 1,010 changed lines to about 420. One task per agent produces smaller PRs, and smaller PRs are easier to review. **Per changed line, the gain is 3.3x.** That's the more conservative number, and the one I'd quote.

Two more figures put that in proportion:

- **Cache reads are 95 to 98% of all tokens**, before and after. The agents mostly re-read what they already have.
- **Output tokens per PR barely moved**: about 130k before and 140k after. The agents write about as much per change as they did before. What fell is what they read to get there.

The coordinator's share of all tokens fell from 14% to 11%, and to 7% in W45.

### Almost all of it came in one step

Tokens per merged PR fell from W40 to W41 and have stayed at 17–28M since. That step was the move to short-lived agents with short handoffs and a context ceiling (finding 2).

The later fixes show up in the fresh tokens, the ones not read from cache. Cache writes per merged PR fell from 0.92M in W41 to 0.40M in W45, as the cache-lifetime fix and the smaller memory index took hold. Fresh tokens are a small share of the count, but each one costs far more than a cache read, so they matter more than their count suggests.

W42 is the high point after the step, at 28M per PR. That was the week routine work ran on a smaller model. Implementation later moved back to the strongest model for quality, and the weeks after are lower. I didn't isolate the cause. Harder work also pushed the other way: as the easy issues ran out, the remaining ones were larger and touched more of the system.

Since W41, moving the routine work of running the fleet into a program cut the coordinator's own tokens per PR by about two thirds and made the fleet far more reliable. It barely moves the fleet-wide figure, though, because the coordinator is a small share of the total.

## 1. Measure from your transcripts, per unit of work

Without a meter, my intuition about where the tokens went was mostly wrong. The meter was already there.

### Your agent's transcripts are already on your disk

Something many people don't realize: Claude Code keeps a complete transcript of every session. They live under `~/.claude/projects/`, in one folder per project directory, as one JSON Lines file per session (`<session-id>.jsonl`). Sub-agents that a session starts get their own files in a `subagents/` folder next to it.

Each line is one record: a message from you, a tool call the agent made, the tool's result (the file it read, the command output it got back), or a piece of the model's reply. Every record has a timestamp, the working directory and the git branch. Model replies also name the model and carry a `usage` block with the token counts for that call:

```json
"usage": {
  "input_tokens": 2,
  "cache_creation_input_tokens": 23470,
  "cache_read_input_tokens": 26124,
  "output_tokens": 468,
  "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 23470}
}
```

That's everything you need to see exactly where your tokens go, call by call, with no guessing and no extra instrumentation. (It's also a full record of every file and command output the agent saw, so treat the folder as sensitive.) Other agent tools keep similar logs; check where yours writes them.

I used the transcripts in four ways, all with plain scripts and no model calls:

- **Totals per day, per model and per kind of agent**, summed over every call. That's the meter for everything in this article.
- **Context over time** for each agent: how big the conversation was on each call, and how long it ran.
- **What the turns were spent on**: reading files, editing, running tests, waiting. That's how I found, for example, that long implementation runs spend most of their turns reading one small piece at a time.
- **Re-pricing the real history as if a change were already in place**, to estimate what a change would save before building it.

The token kinds in the `usage` block don't cost the same, as described above, and cache reads are so numerous that a raw count makes them look like everything. So the shares in this section weight each kind by its price. The results above count raw tokens.

Two things about the method matter more than they look:

1. **Count each request once.** One request appears in a transcript as several records, one per content block, each carrying a copy of the usage; deduplicate by the request id. My first daily script counted every record, and its daily figure was about a third too high. Check the meter before you trust the savings.
2. **Divide by work done, not by time.** Tokens per hour is a budget signal. Tokens per merged PR is the efficiency signal. On the first day after the biggest change, hourly token use didn't move at all — but merged PRs per hour went from 0.57 to 2.06. The saving went into throughput.

The first breakdown, weighted by price:

- **The agent's brief was 0.6% of token use**, although shortening it was the first thing I had tried.
- **File reads were about 27%**, a long tail with no single hotspot.
- **The agents' own output was about 26%.**
- **The system prompt and tool definitions were about 15%.**
- An outside estimate of file-read token use was off by 5x because of a parsing bug.

A second measurement explains where the waste actually was. I measured how much of the carried context was ever used again, and almost all of it was: only 1.5 to 3% was never referenced again. So the waste wasn't irrelevant content. It was *relevant* content carried across hundreds of requests. Re-reading a file once, when it's needed, costs one cache write. Carrying it costs a cache read on every request — much cheaper each time, but repeated. After about a dozen requests, carrying loses.

## 2. Hand off instead of compressing

One agent, one task, then it ends. This change accounts for most of the 5.5x: tokens per merged PR fell from 106M in W40 to 19M in W41, and have stayed between 17M and 28M since.

When an agent's work isn't finished, it doesn't keep going in an ever-growing conversation. Its state goes to durable places instead:
- the code goes to a pushed branch;
- the plan goes to a short status comment on the PR, with the exact next steps, links and the head commit.

A fresh agent starts from that. Its handoff is under 30 lines.

This is enforced by a hook, not by an instruction. The hook watches each agent's context size. At a soft threshold, the agent is told to hand off at its next commit. At a hard threshold, only state-saving commands still run: commit, push, and post a status comment.

On the first day, the median context per agent request fell from 218k to 101k tokens. It fell for every kind of agent: implementation went from 331k to 143k, review from 149k to 90k. The share of agents that ever went past 150k fell from 73% to 25%.

This beats in-context compression because the summary is deliberate, short and auditable. It survives crashes, usage limits and account switches, and a human or another agent can read it. A fresh agent pays for its orientation once, typically tens of thousands of tokens, and earns it back within a few calls.

## 3. Keep the prompt cache warm, and load less into every agent

Prompt-cache expiry was the next-largest drain. When an agent waited more than five minutes — for CI, a long test, or a polling loop — its prompt cache expired, and the next call re-sent the whole context as a cache write. That happened about 800 times a day, and it was **about 31% of all agent usage**.

The fix was mechanical: wait helpers return before 270 seconds, and a guard refuses longer foreground waits. Cache expiry fell to 0.7%.

The same experiments showed that polling isn't the waste it looks like. A poll inside the cache lifetime keeps the cache warm, and a cold restart costs about ten times as much as a poll. The real lever is taking long waits out of an agent's life altogether.

### Stop loading what most agents don't need

Every agent's first message carried about 10k tokens of shared context: the project instructions, plus an always-loaded memory index that had grown to about 90 lines. Most of those lines were orchestration rules that only the coordinator needed.

Worse, that shared context sat after the last cache breakpoint, in the same block as each agent's own task prompt. A one-word difference in the task missed the cache for the whole block. Across 1,411 agents in one day, the median first turn read 3.2k tokens from cache and wrote 11k fresh.

The index now holds 8 universal lines. The rest moved into secondary indexes that an agent opens only when its task needs them. The first-turn cache write fell from about 11.2k to about 4.5k tokens.

The lesson: anything injected into every agent belongs before the cache breakpoint, or nowhere.

## 4. Don't hand an agent a checklist; write the code

In the first weeks, every incident produced a new rule in a prompt. The prompts grew, and the rules were followed most of the time. But "most of the time", across hundreds of agents a day, means several failures a day. And every agent pays, in tokens, to read every rule on every call.

So I changed the rule about rules: **anything that can be done deterministically moves into code.** A rule becomes a gate, a test, a script or a refusal in the tooling, not prose for the model to remember. Some examples of what that looked like in practice:

- **The hourly check and the choice of the next task were checklists for the AI.** Both are now code, which gets its own section below, because it changed reliability as much as tokens.
- **"Don't merge without an approving review" was a sentence.** Now the merge tooling checks for an approving verdict *at the PR's current head commit*, and the reviewer isn't trusted to say so.
- **"Never write into the main checkout" was a sentence.** Now the tool call is refused.
- **"Keep the brief short" was advice.** Now the script that renders a brief from an issue refuses one that cites more source than an agent can read in one go, and says what to cut.
- **"Don't wait longer than five minutes" was advice.** Now the guard from the cache section refuses the wait.
- **Every rule in the contributor guide has a delivery class.** It's either enforced by a gate (whose failure message names the rule), triggered (an agent whose change touches the matching files is told about it, as a pointer rather than the full text), core (every change reads it) or review-only (a reviewer applies it as judgment). A check refuses a rule with no class, and refuses a change that quietly lowers the number of enforced rules.
- **The list of checks is generated from the code.** Nobody has to know or remember where the checks are, and the list can't drift from what actually runs.
- **Fire drills prove the gates still bite.** A gate that never refuses anything might simply be broken.

I used a hospital analogy for this idea in an [earlier article on query execution](https://www.elastic.co/search-labs/blog/agentic-ai-search-deterministic-guardrail-query-execution). There, the model proposes a query and deterministic code decides what actually runs. It turns out the same idea governs how the software gets built:

- **The patient chart is the state.** No doctor is expected to remember every patient; whoever is on shift reads the chart. The status comments and issue threads are the chart, and each agent is the clinician on shift.
- **Shift handover is the 30-line handoff.** Wards use a short, structured handover, not a replay of the whole day. A fresh agent with a structured handoff beats a tired agent with a huge memory.
- **Barcode scanning is the gate.** Hospitals stopped relying on the nurse remembering to check the wristband against the prescription; the scanner refuses the wrong drug. The gates refuse the wrong merge.

That's what made the context reduction possible. A smaller context only saves tokens if nothing important lived in it. Once state lives in files and on GitHub, and rules live in code, the model can forget almost everything and the work barely notices.

## 5. Let a program take load off the AI

The biggest checklist of all was running the fleet itself. At first, a model did it: reading the queue, deciding what to start next, writing each brief, launching agents and checking on them every hour. That's a lot of model calls spent on work that doesn't need judgment. And a model doing routine bookkeeping fails in ways a program doesn't: it skips a step now and then, loses count, or stops entirely when something unexpected blocks it. One night, a single permission prompt in that session stopped every check for seven and a half hours, because it was the only thing watching.

Most of that work is deterministic, so it moved into a small program:

- **A queue decides what runs next**, weighted by area, with a fixed number of slots per kind of work. Picking and launching costs no tokens at all.
- **Briefs are rendered from the issue by a script**, not written by a model.
- **Routine checks run on a timer every 15 minutes, with no model involved.** They print one line per finding, and the AI is only woken when a line needs judgment.
- **When something gets stuck, the fix is a rule in the program, with a test**, not a note for the model to remember next time.

What's left for the AI is the part that actually needs it: judgment calls, unusual failures, and deciding what the program should do differently.

The effect shows up in the coordinator's own numbers. Its model calls and tokens per merged PR fell in two steps: once with short-lived agents in W41, and again when the program took over choosing and launching work in W44 and the routine checks in W45.

| Week | Coordinator calls per merged PR | Coordinator tokens per merged PR | Coordinator share of all tokens |
|---|---|---|---|
| W36–W40 (before) | 26–41 | 14–22M | 11–21% |
| W41 | 23.5 | 3.4M | 18% |
| W42 | 19.5 | 2.7M | 10% |
| W43 | 18.3 | 2.5M | 12% |
| W44 (a program picks and launches the work) | 11.7 | 1.7M | 9% |
| W45 (routine checks on a timer, partial week) | 8.3 | 1.2M | 7% |

Throughput held at 590 to 870 merged PRs a week the whole time, so the AI's own share of the work fell by about two thirds without any loss of output. The reliability gain is harder to put in one number, but to me it's the bigger one: the checks run whether or not anyone's session is awake, a program doesn't skip a step, and a stall that has been fixed in code doesn't come back.

## 6. What helps a human developer helps an agent

Almost everything that makes a codebase easier for a *new human developer* also makes it cheaper for an agent. The difference is that a human pays for a confusing codebase in time and frustration, while an agent pays for it in tokens — and an agent is a new developer every single time it starts.

So a lot of the token work ended up being ordinary engineering hygiene, with a gate behind each piece so it stays true:

- **Code maps.** Each package has a generated map with one line per module: the first line of the module's docstring, its main public names, and the HTTP routes it serves. An agent looking for "where does X happen" greps the maps instead of reading through the source tree, so it doesn't need to hold the whole codebase in its context. The maps are generated, not written, so they say nothing the code doesn't, and a test refuses a module whose docstring summary is missing or too long. They're rendered in each checkout rather than committed, because a committed map went stale and caused merge conflicts on PRs whose own changes were fine.
- **Short comments with pointers.** A description of what code does lives in a docstring or comment right beside that code, and it explains what the reader can't see (the constraint, the incident, the threshold) instead of narrating the code. Everything else is a pointer: an issue number, or a path and anchor into the docs, which a gate checks still resolves. An agent reads the long explanation only when it actually needs it.
- **Smaller, more modular files.** Code and doc files are capped at 1,750 lines, and a gate refuses a change that makes an over-cap file bigger. The way out is to split along a real seam, with a short overview and focused modules, so an agent changing one function reads one module rather than a 5,000-line file.
- **Better documentation, in one place.** Each concept has one canonical page, and a check refuses a passage of 20 or more words copied onto two pages. Each page has one audience. The contributor guide is a short table of contents with chapters, and the root instructions file, which loads on every model call, has a byte cap that can only go down.
- **Rules arrive when they're relevant.** Instead of loading the whole rulebook, an agent whose change touches certain files is told which rule sections apply, as file and line ranges it can read.
- **Reading tools that fit how agents read.** A helper prints several ranges of a file in one call, because each extra call re-reads the whole conversation. A long command's output is reduced to the part that matters (only the failing tests, or the tail of a gate run), and a whole-file read of a large file is refused with an outline instead. The latest addition: once a job has read 60k tokens of files, further reads are cut to 2,000 characters, with a pointer to read just the symbol it needs.

I can't give a separate number for most of these. Their effect is spread across every agent run rather than landing on one day. But they're the reason a fresh agent can orient itself in tens of thousands of tokens instead of hundreds of thousands, and that's what makes short-lived agents affordable in the first place.

## 7. Measure quality next to tokens

A token win can hide a quality loss, so I tracked both:

- **Reverts** went from 0–1 a week to 2–4 a week in W42–W44. That's 0.3–0.7% of merges, at four times the volume. W45 has had none so far.
- **Review verdicts per merged PR** went from 1.77 to about 1.6.
- **Fix rounds per merged PR went up**, from 0.80 to between 0.9 and 1.0. A weekly report puts rework at about 20% of agent tokens.

So tokens per PR fell, and churn per PR didn't. For anyone planning their own setup, I think that's the most useful number in this article. The next round of work is on getting a change right the first time, not on making each attempt cheaper.

## Everything I tried, and what each one bought

Here's the full list, including the ones that didn't pay off. "Measured" means before and after on the real transcripts. "Estimated" means I re-priced the real transcripts as if the change were in place, before building it.

| Change | What it targeted | Effect | How I know |
|---|---|---|---|
| Count each request once | The meter itself | The old daily figure was about a third too high | Measured |
| Shorter briefs | The brief | Never mattered: 0.6% of token use | Measured |
| One task per agent, handoffs under 30 lines, a context ceiling enforced by a hook | Context carried per request | Median context per request 218k → 101k on day one; agents ever past 150k 73% → 25%; tokens per merged PR 106M (W40) → 19M (W41) | Measured |
| Wait helpers under 270 s, and a guard on longer waits | Prompt-cache expiry | Expiry went from about 31% of agent usage to 0.7% | Measured |
| Memory index cut from about 90 lines to 8 | Every agent's first turn | First-turn cache write 11.2k → about 4.5k tokens | Measured |
| A smaller context window for the coordinator | The coordinator's own usage | Modelled at up to 2x cheaper, flattening below about 120k; the coordinator's share of all tokens fell from 14% to 7% | Modelled; share measured |
| A blind head-and-tail cap on tool output | Long command output | Didn't work: it cut text the agent later needed about half the time | Estimated |
| Per-command output digests, and refusing whole-file reads of big files | Long output and big files | Estimated at 5–10% before building; shipped, not measured separately since | Estimated |
| A lower handoff ceiling (90–110k) | Context carried | Estimated at 3–12%; below 50k a handoff costs more than it saves | Estimated |
| A mechanical gate before review (CI red, no test, docs drift, behind main) | Review rounds | 71% of blocking findings were mechanical, yet the saving was only about 3% | Estimated |
| No re-review after a pure merge of main | Review rounds | Under 1.5%: most re-reviews follow a real fix | Estimated |
| Every gate failure reported in one run | Fix-and-rerun loops | Estimated at 3–5% | Estimated |
| Routine work on a smaller model | Price per token | Not isolated. W42, the week it ran, is the highest week after the step (28M per PR), and implementation went back to the strongest model for quality | Measured, cause unclear |
| A helper that reads several file ranges in one call | Read turns | Built, but in long runs 4,159 of 6,304 read turns still follow another read, one small call each | Measured: low adoption |
| A helper that applies a batch of edits across files in one call | Edit turns | Built, but in long runs 363 of 1,371 edit turns still follow another edit turn | Measured: low adoption |
| A per-job read budget, with a pointer to a symbol read | File reads late in a job | A job that reached the ceiling held 84k tokens of file reads, 51% of its context; the fix is too new to measure | Problem measured |
| Code maps, short comments with pointers, file-size caps, one home per concept, rules delivered as pointers | Orientation cost | Not measured separately; spread across every run | Not measured |
| Reports on a state change only, never "still waiting" | Coordinator turns | Not measured separately | Not measured |
| A program for the routine work of running the fleet: picking, launching, briefs, checks | The coordinator's own work | Coordinator tokens per merged PR 3.4M (W41) → 1.2M (W45); calls per merged PR 23.5 → 8.3; no more overnight gaps in checking | Measured |

Two things stand out to me in that table. First, the big wins were structural (what an agent carries, and for how long), not the small optimizations. Second, building a helper isn't the same as getting it used. Both batching helpers work, and the agents mostly don't reach for them. The fix there belongs in the brief and in the tooling's defaults, not in yet another helper.

## What didn't work

- **Shortening the brief.** At 0.6% of token use, it was never the problem.
- **A blind cap on tool output.** Cutting long command output to its head and tail removed text the agent later needed about half the time. Per-command digests, such as only the failing tests or only the tail of a gate run, are the version worth building.
- **Fewer review rounds as a goal in itself.** 71% of blocking review findings were mechanical: CI is red, a change has no test, the docs drifted, the branch is behind main. Yet a mechanical gate before review saves only about 3%, and skipping a re-review after a pure merge of main saves under 1.5%, because most re-reviews follow a real fix.
- **Helpers without defaults.** A helper that an agent has to remember to use mostly doesn't get used.
- **Intuition.** A cheap read-only audit of the real transcripts, run by a strong model, found the 31% cache lever that weeks of my own tuning had missed.

## If you run just one agent

Most of the gate machinery pays off with many agents on a large, rule-heavy repository, where the same context is carried across thousands of calls a day. With one session it would mostly be overhead. But the arithmetic is the same for one session as for a dozen, so a few of these lessons apply directly:

- **Look at your own transcripts.** They're already in `~/.claude/projects/`. A short script that sums the `usage` blocks per session will tell you more than any rule of thumb, including mine.
- **One task per session.** Start a fresh session (or clear the conversation) when you move to the next task, and leave a short note of where you are in a file or an issue. A long-running conversation re-reads everything it has ever seen on every call.
- **Don't walk away from a session mid-task for more than a few minutes**, or leave it waiting on a slow command. When the cache expires, the next call re-writes the whole conversation at the higher price.
- **Keep what loads into every session small.** Project instruction files are read on every call. Put the rule that matters everywhere there, and point to the rest.
- **Make your codebase easy to navigate**: short module summaries, small files, comments that point to the details. It helps the agent for the same reason it helps a new colleague.

## What's next

The implementation job is now about 80% of agent token use, and its longest runs are where the remaining waste is: in a recent 24-hour sample, runs of more than 150 turns took about a third of implementation tokens. Getting those runs to read in bigger, better-aimed pieces, and to get the change right the first time, is the next round.

There's also a problem that volume brings on its own. At team-sized PR volume, the bottleneck moves from writing code to *landing* it. A merge queue tests PRs in groups against the latest main, and one failing PR drops its whole group. That deserves its own article.
