---
showtoc: true
title: "Six changes that cut Claude Code token use per merged pull request 3.5x"
date: 2026-11-07
draft: true
slug: agent-fleet-token-efficiency
tags: ["ai", "agents", "developer-tooling", "claude", "token-efficiency"]
categories: ["AI-Assisted Development"]
description: "Why coding agents use so many tokens, how to measure it from the transcripts already on your disk, and the changes that cut tokens per merged pull request 3.5x on a project with a significant amount of AI-written code."
---

## Summary

I have a project with a significant amount of code written by AI agents. With four agents running, a full weekly token allowance lasted about a day.

Six changes later, the same work takes 3.3 to 5.5 times fewer tokens, so at the old pace that allowance would last three to five and a half days instead of one. Output did not fall to get there: each week the agents now merge more PRs and change more lines than before. This article explains where the tokens went, how I fixed it, and what each change brought, including the changes that brought nothing.

Measured over ten weeks and about 1.36 million model requests:

- **Tokens per merged pull request in the main repository fell 3.5x**, from about 133 million to about 38 million.
- **Per changed line, they fell 3.3x**, from about 85,000 to about 26,000.
- **Merged PRs per week rose 4.4x**, on 19% fewer tokens a week.
- **Reverts stayed rare** (0.2 to 0.7% of merges), but rework per PR did not fall.

Across all four repositories the agents work in, the drop is 5.5x per merged PR. The headline uses the smaller number; [the results](#the-results) say why.

The cost comes from one fact: the model has no memory, so every call re-sends the whole conversation, and the tokens used are roughly the number of calls times the context carried. Everything that helped reduced one of those two factors. What I changed, and what each change brought:

1. **Measure from the transcripts**, per merged PR, not per hour. This saved nothing by itself, but it found the levers. One of them, cache expiry while agents waited, was 31% of all agent usage, and my first guesses had missed it.
2. **End each agent after one task**, with a short written handoff and a context ceiling enforced by a hook. This was the big step. On the first day, the median context per agent request fell from 218k to 101k tokens, and tokens per merged PR fell from 106M in W40 to 19M in W41, together with the first cache fix in 3.
3. **Keep the prompt cache warm**, and load less into every agent. Cache expiry fell from 31% of agent usage to 0.7%, and the fresh tokens an agent writes on its first turn fell from about 11k to 4.5k.
4. **Turn rules into code**, so the model does not have to remember them. Fewer rules in every prompt, and fewer failures; I have no separate number for it.
5. **Let a program take load off the AI** for the routine work of running the fleet. The coordinator's tokens per merged PR fell from 14–22M to 1.2M, and its checks now run while my session sleeps.
6. **Make the codebase easy for a new developer**, because every agent is one. No separate number either; it is what makes a fresh agent's start cheap enough for one task per agent.

The principle behind all six: don't make the model remember; make the system remember.

This is one project, run by one person, with several changes landing at once. Where I cannot separate their effects, I say so.

## What to do first

The arithmetic is the same for one session as for a dozen agents. Without a fleet, these five steps cover most of it:

- **Measure.** [The script in the appendix](#appendix-a-script-to-sum-tokens-per-session) sums each session's tokens from the transcripts Claude Code keeps under `~/.claude/projects/`, counting each request once.
- **One task per session.** Start fresh for the next task, with a short note of where you are; a long conversation re-reads everything on every call.
- **Don't leave a session idle past its cache lifetime** (an hour for an interactive subscription session, five minutes for sub-agents and API use), and run anything slow in the background.
- **Keep what loads into every session small**: only the rules that apply everywhere, with pointers to the rest.
- **Make the codebase easy to navigate**: short module summaries, small files, comments that point to the details.

On my coordinating session, a few days old, that script shows about 3,600 calls, 534 million cache-read tokens and 2.3 million output tokens. The ratio between the last two is the subject of this article. The gates and the scheduling program below pay off only with many agents on a large, rule-heavy repository.

## The setup

One coordinating session watches the work. Up to a dozen background agents on a single cloud VM each take one GitHub issue, write the change and its tests in their own clone, and open a pull request. A separate review agent, told to look for reasons *not* to merge, must approve every PR at its current head commit, and the PR then lands through a merge queue with green CI.

The main repository is a multi-service search product, mostly Python and TypeScript, with about 1,800 source files (excluding tests) and about 135 CI jobs. The agents also work in three smaller repositories: a data generator and two demo configurations. The fleet now merges 590 to 870 PRs a week across the four.

## Why agents use so many tokens

It takes three ideas: a call, the conversation sent with each call, and the cache.

### One call: the model writes its response one token at a time

A *call* is one request to the model: the program sends text, and the model sends back one response. A *token* is a word or a piece of a word.

The model writes its response one token at a time. Each new token is predicted from the whole history: all the text it was sent, plus the tokens it has already written. The new token is then added to that history, and the next one is predicted from all of it. In the figure, step 4 predicts "cart.py" from the system prompt, the tool list, your message and "Let me read". [The Illustrated GPT-2](https://jalammar.github.io/illustrated-gpt2/) shows this step by step.

![Inside one call: the model predicts "Let", then "me", then "read", then "cart.py". Each prediction reads the whole history so far, and each new token is added to the history before the next token is predicted](images/one-call.svg)

Done literally, that would be slow. A 500-token response to a 100k-token input would push those 100k tokens through the network 500 times. So, for efficiency, the model does not push the whole history through the network again for every token. When the call starts, it processes the input once and keeps the intermediate results for every token (the [KV cache](https://huggingface.co/blog/not-lain/kv-caching)). Each new token then goes through the network on its own and attends to those stored results, so it is still predicted from the whole history. The output is the same as recomputing everything, only faster. A call is accordingly billed once for its input, plus once for each token of its response. When the call ends, the stored work is discarded. Keep that in mind: an agent makes many calls, and each one starts again from nothing unless the provider kept that work (the cache, below).

### Many calls: the agent sends the whole conversation again, every time

The model has no memory between calls. Each time, the program sends the whole conversation so far: the system prompt, the tool definitions, every message and every result. [Claude Code's documentation](https://code.claude.com/docs/en/prompt-caching) says it directly: "The model doesn't remember anything between requests, so Claude Code re-sends the full context."

In a chat, that happens once per message you type. An agent supplies its own next input. The model cannot open a file or run a test; it can only write text. So when it needs something, its response ends with a [tool request](https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview) such as `Read(cart.py)` or `Bash(pytest)`. Claude Code carries it out on your computer and keeps what came back, the *tool result*: the text of the file, or what the test run printed. It adds the response and the tool result to the conversation and makes the next call straight away.

![Across calls: each call sends everything so far, plus a new response and tool result; over 200 calls the area is all the input tokens](images/agent-loop.svg)

So one message from you ("fix this test") can become 50 or 200 calls, each re-sending everything so far. An agent that starts at 20k tokens and grows to 150k carries about 85k on an average call. Over 200 calls, that is about 17 million input tokens, against perhaps 0.1 million tokens of responses, although the final conversation is only 150k long.

**Tokens used are roughly the number of calls times the context carried.** Double either and you double the total; the brief an agent starts from is small by comparison.

### The cache: keeping the work between calls

Call 101 is call 100 plus one response and one tool result. The provider can keep the stored work of the previous call for a while, so that only the new part is processed. That is [prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching): the same stored work as inside a call, kept between calls.

| | What is added each time | Is the earlier work reused? |
|---|---|---|
| Inside one call | one token | always (the KV cache) |
| From one call to the next | a response and a tool result | only while the prompt cache is alive |

Reading a cached prefix costs a tenth of the normal input price or less, depending on the model. Writing a prefix into the cache costs 1.25 times the normal price for a five-minute cache, or twice the price for a one-hour cache, and every use resets the clock. Claude Code gives the interactive session on a subscription a one-hour cache; sub-agents, where most of this fleet's tokens go, get five minutes.

Three consequences shaped everything that follows:

- **Cache reads dominate the token count**: 94 to 98% of all tokens in this fleet, because every call re-reads the conversation so far.
- **Cheap per token is not cheap in total.** Weighted by price, cache reads were about three quarters of the cost before the changes and about half after.
- **A cache miss is expensive.** An agent that sits idle past the cache lifetime pays the write price for the *entire* conversation on its next call.

## The results

The figures come from one script over every transcript on both machines, about 1.36 million model requests. Every token counts once: fresh input, cache writes, cache reads and output. The script was checked against a baseline recorded at the start, for 15 September to 3 October, and agreed within 2.3%. Weeks are ISO weeks; W45 is partial, to 7 November.

Changed lines are additions plus deletions, from all four repositories. A few PRs a week regenerate data files and change tens of thousands of lines, so for tokens per line, a PR counts at most 5,000 lines.

| Week | Merged PRs (all / main repo) | Tokens | Tokens per main-repo PR | Tokens per merged PR (all) | Median PR size (lines) | Tokens per changed line |
|---|---|---|---|---|---|---|
| W36 | 195 / 195 | 19.6B | 101M | 101M | 915 | 84k |
| W37 | 153 / 153 | 16.3B | 106M | 106M | 998 | 82k |
| W38 | 113 / 96 | 12.9B | 134M | 114M | 1,132 | 72k |
| W39 | 151 / 100 | 23.3B | 233M | 154M | 1,078 | 97k |
| W40 (changes begin) | 196 / 171 | 20.7B | 121M | 106M | 1,132 | 58k |
| W41 | 632 / 508 | 12.2B | 24M | 19M | 489 | 21k |
| W42 | 871 / 522 | 24.4B | 47M | 28M | 467 | 31k |
| W43 | 587 / 253 | 12.4B | 49M | 21M | 347 | 33k |
| W44 | 670 / 281 | 11.9B | 42M | 18M | 394 | 21k |
| W45 (partial) | 641 / 330 | 11.9B | 36M | 19M | 411 | 23k |

**Before** (W36–W39): 133M tokens per main-repo PR, 118M per merged PR across all repositories, 85k per changed line. About 150 merged PRs and 18 billion tokens a week.

**After** (W41–W45): 38M tokens per main-repo PR, 21M per merged PR across all repositories, 26k per changed line. About 680 merged PRs and 15 billion tokens a week.

### Why the headline is 3.5x and not 5.5x

Across all four repositories, tokens per merged PR fell 5.5x. But the mix of repositories changed: the main repository was 89% of merged PRs before and 56% after, and PRs in the smaller repositories are smaller (configuration and data changes). Part of the 5.5x is that shift, not efficiency.

The 3.5x charges every token, including those spent in the other three repositories, to main-repository PRs alone. That overstates the cost per PR after the change, so 3.5x is a floor. The per-line figure, 3.3x, is far less sensitive to the mix and agrees with it. W45 is partial: the complete weeks W41–W44 alone give 3.4x.

PRs also got smaller. The median fell from about 1,010 changed lines to about 420, and the average, with each PR capped at 5,000 lines, from about 1,400 to about 850. One task per agent produces smaller PRs, which are easier to review.

Smaller PRs alone would lower tokens per PR without any real gain, so the figure that settles it is tokens per changed line, which does not depend on how the work is split into PRs. It fell 3.3x: the same amount of changed code now takes less than a third of the tokens. Smaller PRs come on top of that, which is why tokens per merged PR across all repositories fell further, 5.5x.

### What changed, and what I cannot separate

Almost all of the drop happened between W40 and W41. Two changes landed together: short-lived agents with a hook-enforced context ceiling, and a cap on waits that stopped cache expiry. I did not run them separately, so I cannot divide the step between them. The direct evidence is the context distribution: on the first day of the ceiling, the median context per agent request fell from 218k to 101k tokens.

The model mix changed too, but earlier. By W40, 92% of tokens were already on the newer Opus generation, at 121M per main-repo PR, so the generation change alone did not produce the step. In W41 a smaller model also took 27% of tokens, and 69% in W42.

The later weeks moved for reasons I also did not isolate. W42 and W43, the highest weeks after the step, are the weeks a smaller model carried more than half the tokens; implementation then went back to the strongest model for quality. As the easy issues ran out, the remaining ones were larger, which pushes the per-PR figure up. Cache writes per merged PR fell from 0.92M in W41 to 0.40M in W45, as the later cache fixes took hold.

### What did not change, or got worse

- **Output tokens per PR barely moved**: about 130k before and 142k after. The agents write about as much per change; what fell is what they read to get there.
- **Reverts** rose from 0–1 a week to 2–4 a week in W42–W44, 0.2 to 0.7% of merges at four times the volume.
- **Fix rounds per merged PR rose**, from 0.80 to 0.9–1.0, and the weekly reports put rework at about 20% of agent tokens.
- **"CI is red" review findings** rose from 15% to 26% of blocking findings after the cache fix.
- **The fixed context of an agent's first turn grew** from 9.9k to 14k tokens over the same period.

Tokens per PR fell; rework per PR did not. That is where the next round of work is.

At list prices, the cost per merged PR fell from about $72 to about $9.50 across all repositories. That is a list-price equivalent, not a bill: the fleet runs on subscription plans, and the drop is larger than the token drop because the newer models cost less per token.

## 1. Measure from the transcripts, per unit of work

My first guesses about where the tokens went were wrong; the transcripts on disk already held the answer.

Claude Code keeps a complete transcript of every session under `~/.claude/projects/`: one folder per project directory, one JSON Lines file per session (`<session-id>.jsonl`), and the sub-agents' files in a `subagents/` folder next to it. Each line is one record: a message from you, a tool call, a tool result, or part of the model's response. Every message record has a timestamp, the working directory and the git branch, and each response carries a `usage` block for its call:

```json
"usage": {
  "input_tokens": 2,
  "cache_creation_input_tokens": 23470,
  "cache_read_input_tokens": 26124,
  "output_tokens": 468,
  "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 23470}
}
```

Tools such as [ccusage](https://github.com/ryoppippi/ccusage) read the same files, and [the appendix](#appendix-a-script-to-sum-tokens-per-session) has a short script that does it. The folder is also a full record of every file and command output the agent saw, so treat it as sensitive.

Two details of the method matter more than they look:

1. **Count each request once.** One request appears as several records, one per content block, each with a copy of the usage. My first daily script counted every record, and its figure was about a third too high.
2. **Divide by work done, not by time.** Tokens per hour is a budget signal; tokens per merged PR is the efficiency signal. On the first day of the context ceiling, hourly token use did not move, but merged PRs per hour went from 0.57 to 2.06. The saving went into throughput.

The first breakdown, weighted by price, from one day's transcripts: the brief was 0.6% of use, file reads about 27%, the agents' own output about 26%, and the system prompt and tool definitions about 15%.

A second measurement, from one day's transcripts, showed where the waste was. Of the context an agent carried, only 1.5 to 3% was never referenced again. The waste was not irrelevant content; it was relevant content carried across hundreds of calls. Reading a file again when it is needed costs one cache write. Carrying it costs a cache read on every call, cheaper each time but repeated, and after about a dozen calls carrying costs more.

## 2. End each agent after one task, with a written handoff

When an agent's work is not finished, it does not continue in an ever-growing conversation. The code goes to a pushed branch, and the plan goes to a status comment on the PR with the next steps, links and the head commit. A fresh agent starts from that handoff, which is under 30 lines.

A `PreToolUse` hook enforces it for every sub-agent. Before each tool call it reads the agent's current context size from its transcript. At 150k tokens it adds a note: at the next commit, push, post the status comment and end. At 200k it refuses every tool call except the `git` and `gh` commands a handoff needs, and the refusal text carries the handoff steps.

On the first day, median context per request fell for every kind of agent: implementation from 331k to 143k tokens, review from 149k to 90k. The share of agents that ever passed 150k fell from 73% to 25%.

A written handoff beats in-context compaction for three reasons I can check: it is short, a human or another agent can read it, and it survives a crash, a usage limit or an account switch. A fresh agent pays for its orientation once, typically tens of thousands of tokens.

## 3. Keep the prompt cache warm, and load less into every agent

When an agent waited more than five minutes, for CI, a long test or a polling loop, its cache expired and the next call wrote the whole context again. In one day's measurement that happened about 800 times and was **about 31% of all agent usage**.

Wait helpers now return before 270 seconds, and a guard refuses longer foreground waits. Cache expiry fell to 0.7% of agent usage. Polling turned out not to be the waste it looks like: a poll inside the cache lifetime keeps the cache warm, and a cold restart costs about ten times as much as a poll.

The second fix was in what every agent loads. Each agent's first message carried an always-loaded memory index of about 90 lines, appended to the first user message, after the last cache breakpoint. Most of its lines were rules only the coordinator needed. Because it sat in the same block as each agent's own task, a one-word difference in the task missed the cache for the whole block: across 1,411 agents in one day, the median first turn read 3.2k tokens from cache and wrote 11k fresh.

The index now holds 8 universal lines, and the rest moved to secondary indexes an agent opens only when its task needs them. The first-turn cache write fell from about 11.2k to about 4.5k tokens. Anything injected into every agent belongs before the cache breakpoint, or nowhere.

## 4. Turn rules into code

In the first weeks, every incident produced a new rule in a prompt. The rules were followed most of the time, but across hundreds of agents a day, most of the time means several failures a day, and every agent pays to read every rule on every call.

So anything that can be checked deterministically moved into code, as a gate, a test, a script or a refusal in the tooling:

- **"Don't merge without an approving review" and "never write into the main checkout"** were sentences. The merge tooling now checks for an approving verdict at the PR's current head commit, and a write into the main checkout is refused.
- **"Keep the brief short"** was advice. The script that renders a brief from an issue now refuses one that cites more source than an agent can read in one go, and says what to cut.
- **Every rule in the contributor guide has a delivery class**: enforced by a gate whose failure message names the rule, triggered (an agent touching the matching files gets a pointer to it), core, or review-only. A check refuses a rule with no class.

I described the same idea for query execution in an [earlier article](https://www.elastic.co/search-labs/blog/agentic-ai-search-deterministic-guardrail-query-execution): the model proposes, deterministic code decides what runs. Here it applies to how the software is built. A smaller context saves tokens only if nothing important lived in it. Once state lives in files and on GitHub, and rules live in code, the model can forget almost everything between agents, and the work does not notice.

## 5. Let a program take load off the AI

The largest checklist was running the fleet itself. At first a model did it: reading the queue, choosing the next task, writing each brief, launching agents and checking on them every hour. That is many model calls for work that needs no judgment, and a model doing bookkeeping skips a step now and then or stops when something blocks it. One night a single permission prompt in that session stopped every check for seven and a half hours.

Most of that work moved into a small program:

- **A queue decides what runs next**, weighted by area, with a fixed number of slots per kind of work. Choosing and launching costs no coordinator tokens.
- **Briefs are rendered from the issue by a script.**
- **Routine checks run on a timer every 15 minutes, with no model.** They print one line per finding, and the AI is woken only for a line that needs judgment.
- **A stall is fixed by a rule in the program, with a test**, not a note for the model.

The coordinator's own numbers fell in two steps, coinciding with the short-lived agents in W41 and with the program taking over the work in W44 and W45:

| Week | Coordinator calls per merged PR | Coordinator tokens per merged PR | Coordinator share of all tokens |
|---|---|---|---|
| W36–W40 | 26–41 | 14–22M | 11–21% |
| W41 | 23.5 | 3.4M | 18% |
| W42 | 19.5 | 2.7M | 10% |
| W43 | 18.3 | 2.5M | 12% |
| W44 (a program chooses and launches) | 11.7 | 1.7M | 9% |
| W45 (checks on a timer, partial) | 8.3 | 1.2M | 7% |

Throughput held at 590 to 870 merged PRs a week. Because the coordinator is a small share of all tokens, this barely moves the fleet-wide figure. The larger gain, to me, is reliability: the checks run whether or not my session is awake, and a stall fixed in code does not come back.

## 6. Make the codebase easy for a new developer

What makes a codebase easier for a new human developer also makes it cheaper for an agent. A human pays for a confusing codebase in time; an agent pays in tokens, and an agent is a new developer every time it starts. Each of these has a gate behind it so it stays true:

- **Code maps.** Each package has a generated map, one line per module: its docstring summary, main public names and HTTP routes. An agent greps the maps instead of reading through the tree.
- **Short comments with pointers.** A comment explains what the reader cannot see (the constraint, the incident, the threshold) and points to an issue or a doc anchor for the rest; a gate checks the pointer resolves.
- **Small files.** Code and doc files are capped at 1,750 lines, and a gate refuses a change that makes an over-cap file bigger.
- **One home per concept.** A check refuses a passage of 20 or more words copied onto two pages, and the root instructions file, loaded on every call, has a byte cap that can only go down.
- **Reading tools that fit how agents read.** A helper prints several file ranges in one call, command output is reduced to the part that matters, and once a job has read 60k tokens of files, further reads are cut to 2,000 characters with a pointer to read just the symbol needed.

I cannot give a separate number for these; their effect is spread across every run. They are what makes a fresh agent's orientation cheap enough for one task per agent.

## What did not pay, and what I could not measure

"Estimated" means re-pricing the real transcripts as if the change were in place, before building it.

| Change | Effect | How I know |
|---|---|---|
| Shorter briefs | Never mattered: the brief was 0.6% of use | One day |
| Blind head-and-tail cap on tool output | Did not work: cut text the agent needed about half the time | Estimated |
| Per-command output digests, refusing whole-file reads of big files | 5–10%; shipped, not measured separately | Estimated |
| A lower handoff ceiling (90–110k) | 3–12%; below 50k a handoff costs more than it saves | Estimated |
| A mechanical gate before review | 71% of blocking findings were mechanical, yet only about 3% saved | Estimated |
| No re-review after a pure merge of main | Under 1.5%: most re-reviews follow a real fix | Estimated |
| A helper that reads several file ranges in one call | Built, but in one sample of long runs two thirds of read turns still followed another read | One sample: low adoption |
| A per-job read budget with a pointer to a symbol read | Too new to measure | Not yet measured |
| Code maps, pointer comments, file caps, one home per concept | Spread across every run | Not measured |

A helper that an agent has to remember to use mostly does not get used; it belongs in the tooling's defaults. And a read-only audit of the real transcripts by a strong model found the 31% cache lever that my own tuning had missed for weeks.

## Prior work

Most of the mechanics are documented. Claude Code's [cost](https://code.claude.com/docs/en/costs) and [prompt-caching](https://code.claude.com/docs/en/prompt-caching) pages explain the re-sent context and the cost of a cache miss. Manus [called](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) the KV-cache hit rate the single most important metric for an agent. Handing off instead of compacting is the idea behind [Amp's handoff](https://ampcode.com/news/handoff) and HumanLayer's [context engineering for coding agents](https://www.humanlayer.dev/blog/advanced-context-engineering), and hooks for deterministic control are in the [hooks guide](https://code.claude.com/docs/en/hooks-guide). What I have not found elsewhere is the measurement: tokens per merged PR over ten weeks and 1.36 million requests, the share of usage lost to idle cache expiry, the context distribution under a hook-enforced ceiling, and quality tracked next to tokens.

## What's next

The implementation job is now most of agent token use, and in one 24-hour sample, its runs of more than 150 turns took about a third of implementation tokens. Getting those runs to read in larger, better-aimed pieces, and to get the change right the first time, is the next round.

Volume brings its own problem. At this PR volume, the bottleneck moves from writing code to landing it: a merge queue tests PRs in groups against the latest main, and one failing PR drops its whole group. That deserves its own article.

Measure tokens per merged PR, enforce a context ceiling, and take the long waits out of an agent's life. Everything else in this article was worth less than those three.

## Appendix: a script to sum tokens per session

It reads the ten most recent session transcripts under `~/.claude/projects/` and prints each session's calls and tokens, counting each request once.

```python
import json, glob, os
from collections import defaultdict

# Sum token usage per Claude Code session, counting each request once.
root = os.path.expanduser("~/.claude/projects")
for path in sorted(glob.glob(f"{root}/**/*.jsonl", recursive=True), key=os.path.getmtime)[-10:]:
    seen, tot = set(), defaultdict(int)
    for line in open(path, errors="ignore"):
        try: rec = json.loads(line)
        except ValueError: continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
        u, rid = msg.get("usage"), rec.get("requestId")
        if not u or rid in seen: continue
        seen.add(rid)
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            tot[k] += u.get(k) or 0
    if seen:
        print(os.path.basename(path)[:36], "calls", len(seen), dict(tot))
```
