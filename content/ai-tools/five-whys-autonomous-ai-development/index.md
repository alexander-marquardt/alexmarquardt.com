---
showtoc: true
title: "The power of the five whys in autonomous AI development"
date: 2026-11-23
draft: true
slug: five-whys-autonomous-ai-development
tags: ["ai", "agents", "developer-tooling", "claude", "engineering-productivity"]
categories: ["AI-Assisted Development"]
description: "Coding agents that fix failures around the clock tend to stop at the mechanism that broke. A required, evidenced chain of whys, enforced by a gate, pushes them on to the missing test, rule or design decision. How the rule works, a worked example, and what the first 195 chains show, including where they fall short."
---

A fleet of coding agents on the project I work on fixes failures around the clock, mostly with nobody watching. Two earlier articles covered [the guardrails](/ai-tools/coding-agents-codebase-under-control/) and [the token cost](/ai-tools/agent-fleet-token-efficiency/). This one is about a single habit the fleet has to be forced into: asking why more than once.

An agent's first explanation of a failure is usually the mechanism. "The write door refused the call." "The cache was not cleared." That is often true, and fixing it makes this occurrence go away. It does not say why the mechanism was in place, or why nothing noticed. The same class of failure then comes back somewhere else, and because no person is watching, nobody connects the two.

The fix is an old idea, the five whys from Toyota's production system, with two changes to suit agents: each answer must carry evidence, and a program refuses the work until it does.

## The rule

Every failure the fleet records (a red main branch, a flaky test, a stalled pull request, a wrong counter, a failed gate) must carry a section headed `### Why chain`, with numbered steps. Each step answers why the step before it happened. Each step must do one of two things:

- **Cite evidence a reader can open:** a log line, a commit, a run, an issue, a path in the code.
- **Say `hypothesis:`** and name the experiment that would settle it. The step stays open until it carries a `Result:`.

The rule began as three steps on 15 November (the filing gate merged the next day) and was raised to five on 23 November, in force for issues filed from 14:00 UTC that day.

Two gates enforce it. One refuses to file a failure issue whose chain is incomplete. The other refuses a pull request that says it closes such an issue. A mitigation can still land beside the diagnosis, but it must say it only refers to the issue, so the issue stays open and the question stays asked. An issue filed under the older rule keeps the older minimum, so the change did not refuse work already in flight.

## Why the questions cannot be scripted

It is tempting to write the five questions down: what broke, why did it break, who changed it. That does not work, because each why asks about the previous answer, and the previous answer is not known in advance. A fixed list turns the chain into a form, and an agent will fill in a form.

Two kinds of step have to appear, though, whatever the questions were:

- **Why was this not caught?** The missing test, check or review.
- **Why was this not prevented?** The design or the process that allowed it.

A chain that has neither stops at what broke. These two are what take it from the failure to the system that let it happen.

## Where to stop

Five is a floor, not a goal. The chain can end sooner in two cases:

- **At a cause outside the fleet's control**, such as a vendor outage, marked `External:` with evidence. There is nothing further to change.
- **At the change that prevents the whole class**, marked `Class fix:` with evidence, from the fourth step on. A class fix named at step two is usually a fix for this occurrence with a bigger name.

Stop when the answer is a fix that would have prevented every failure of this kind, not only the one in front of you.

## A worked example: the stale trigger match

The search engine in this project keeps its search policies in memory and matches each query against them. On 23 November a Studio screen showed a warning that its engine and the search cluster disagreed on one query, "leather boots". The engine was still applying a policy that had been deleted about ten hours earlier.

The chain, with five steps:

1. **Why did the engine match a deleted policy?** It held an old copy of the policy set. The same query on the live index gave the right answer, so the matcher itself was correct.
2. **Why was the old copy never replaced?** An engine reloads its policies when it receives a refresh signal, and none arrived.
3. **Why did none arrive?** The fleet's write door, the program every write to the shared cluster goes through, refused to send it. Its own log showed no refresh signal ever sent, and 19 skipped.
4. **Why does the door refuse it?** Its rule was written for writes to an index a job had made for itself, which no engine serves. Writing in place to the index that engines do serve came later, and the rule was not revisited.
5. **Why did nothing catch it?** No test makes a write to a served index and then checks that a running engine follows it.

Stopping at step three fixes the door. The next rule written before a later feature stays in place, and the next lost signal is as silent as this one. Step four says which other rules to look at. Step five adds the test that would have caught this failure, and would catch the next one, whoever causes it.

The chain did not begin this long. The issue as first filed had four steps, and the five-step version is the one written out when the minimum was raised, with this incident as its evidence.

What the fix became shows what the later steps buy. The door fix, the step-three answer, merged the same day. It came with tests that replay the recorded writes and check that each sends a signal. The step-five answer reached further than a test. An engine's cache is now to be invalidated in the same call that records the change, so no writer can log one and forget the other, and a check in test and development is to raise an error whenever an engine is behind the change log. At the time of writing that work is still in review, so I am reporting the design and not its result.

## A gate that checks a minimum gets the minimum

A rule that says "at least three steps" mostly gets three steps. A third step is often enough to pass, and it often names the mechanism, the thing the rule was meant to get past.

From 15 November until the five-step rule merged on 23 November, the two main repositories had 195 issues with a chain:

| Steps in the chain | Issues | Share |
|---|---|---|
| 3 (the minimum) | 154 | 79% |
| 4 | 31 | 16% |
| 5 | 9 | 5% |
| 6 | 1 | <1% |

Two more issues had the heading and no steps. Of the 41 chains longer than three, 10 were filed on 23 November, the day the five-step rule was decided.

The first hours of the new rule show the same pattern one step up. Ten chains were filed in its first eight hours, and all ten have exactly five steps.

They also show the limit of the gate. It checks what it can count: the number of steps, and whether each cites something. It does not check that the last step names the missing test or design. Nor does it check every chain. Eight of those ten are on issues that the gate does not class as failures, so it never looked at them, and six of the eight have a step with no evidence and no experiment. That is a small sample, but it fits the rest: without the gate, agents write the section and let the evidence slide.

The gate also has holes. From 17 to 23 November, 59 issues were filed that the rule classes as failures, and 45 of them (76%) carry a chain today. Some of the rest are filed by a workflow on the code host that does not go through the fleet's gates. A chain filed the same evening, about exactly this, found that the rule had been wired into the fleet's own filing paths only, and that the failure issues other paths file were never listed.

## Does a longer chain stop repeats?

That is the claim, and I cannot show it from the records yet. The obvious test is to ask whether issues whose class came back had shorter chains than the rest. Counting a recurrence as a later issue with the same class title or root cause, a later comment recording another occurrence, or a later issue naming it as the same class, 13 of the 195 recurred:

| | Issues | Exactly 3 steps | Average steps |
|---|---|---|---|
| Class recurred | 13 | 8 (62%) | 3.6 |
| The rest | 182 | 146 (80%) | 3.2 |

The numbers point the other way: recurring issues had slightly longer chains. I do not read this as evidence against the rule, or for it. Twelve of the thirteen are alerts that a build on the main branch is red. Their shared titles, such as "main should be green", cover many different causes, so "same title" does not mean "same class". They are also the most serious failures, and those get longer chains. Thirteen is a small number.

One other figure is clearer. When the fleet's filer finds that a failure matches an open issue, it adds an occurrence comment instead of a new issue. There were 75 such comments since 15 November, on 21 issues, and only one of those issues has a chain. Most of the others are alerts the fleet raised about itself. The repeats the fleet records are mostly on issues outside the rule.

## What I will measure in a week

The five-step rule took effect on 23 November. About a week later I will add the same measures, plus three that need time:

- **Depth:** the share of chains longer than the minimum, and of chains that reach a `Class fix:` or `External:` step.
- **Class-level fixes:** whether the fixes that merge from these chains add a test, gate or rule, and not only a patch.
- **Repeats:** occurrence comments, and recurrence counted by root cause rather than by title.
- **Cost:** tokens per failure issue, since a deeper chain takes more of them.

If chains are five steps long because the minimum is five, and repeats do not fall, I will say so. The test of the rule is not how long the chains are but whether the same thing stops happening.

## What carries over

The rule is not specific to agents. Agents make the need for it plain: they work fast, they do not remember the last time, and they are content with the first true answer. For anyone running agents or a team unattended:

- Require evidence per step. A chain of plausible sentences is easy to write and easy to accept.
- Let a step say it is a guess, if it names the experiment. A forced answer is worse than an open question.
- Ask for the two steps that matter, not caught and not prevented, and let the rest follow from the answers.
- Let the chain end early at an external cause or a class fix. A count nobody can finish gets padded.
- Measure whether the class comes back. A gate can only count, and what it counts becomes the target.

This is one of the duties that keep the fleet running unattended. [Issue 35](https://github.com/alexander-marquardt/alexmarquardt.com/issues/35) lists them, along with the orchestration layer around it. Deadlocks, where a chain of waits stops everything, are [a subject of their own](https://github.com/alexander-marquardt/alexmarquardt.com/issues/28).

<!--
DRAFT NOTES (alexander-marquardt/alexmarquardt.com#37). Not rendered: the page is draft: true.

Before publishing:
- Replace the #35 and #28 issue links with the published articles' URLs.
- Re-check the worked example's "still in review" sentence (elastic/prism#16719, alexander-marquardt/agent-ops#2672).
- Add the one-week follow-up (about 2026-11-30) to "Does a longer chain stop repeats?" and replace "What I will
  measure in a week".

How the figures were counted, on 2026-11-23 about 22:40Z, so that the follow-up counts the same way:
- Every issue (not pull request) created since 2026-11-15T00:00Z in agent-ops and prism, all states. A chain's steps
  are `whychain.steps(body)` from agent-ops `v3/whychain.py`, the gate's own parser; a body can be edited later, so
  these are the bodies as they stood at the count. 1,078 issues before the five-step rule's merge
  (2026-11-23T11:26:07Z). The two with the heading and no steps are outside the 195.
- "Classed as a failure": `whychain.is_failure(body, labels)`. The 17 to 23 November figure is by creation date, from
  the first full day after the filing gate merged (2026-11-16 16:22Z).
- "No evidence and no experiment": `whychain.problems(body, created_at)` on the 10 chains filed after 14:00Z.
- Recurrence: a later issue in the same repository with the same class title (the part before `; currently`, with
  numbers as one token) or the same `Root cause:` line, an "Another occurrence of this class" comment, or a later
  body naming the issue as the same class. Scanned 17,610 comments since 2026-11-15.
- The histogram in agent-ops#2693 (135 chains, 114 of exactly 3) is agent-ops only, counted earlier the same day; this
  article counts two repositories to the merge. agent-ops alone is now 119 of 143.
-->
