#!/usr/bin/env python3
"""The measurements behind the "AI slop" article (issue #32, slice 1).

The article is written from these numbers, not the other way round. This script
reads them from the main repository and the agent fleet's own records and
writes data/slop_measures.json: aggregate counts only, never a commit subject,
an issue title or a repository name.

    python3 scripts/slop_measures.py \
        --repo-dir <clone of the main repository> --repo <owner/name> \
        --work-db <the fleet's work.db> --out data/slop_measures.json

What it measures, and from where:

  weeks      per ISO week since --since, from the first-parent history of
             main: merged PRs (a subject ending "(#N)"), reverts, and main
             repairs (a merged "fix(main-red): ..." that is not a revert), each
             also per 100 merged PRs. Main repairs are counted only from the
             week the "fix(main-red)" convention first appears; before it a
             repair had no marker, so those weeks read null, not 0.
  red        per ISO week since the fleet began recording red spells of main:
             hours main was red, the spells that began that week, and the
             median minutes from red to green of those spells.
  rounds     per ISO week whose every day the job log covers: merged PRs and
             the fix rounds pushed to them (a fix job that ended `pushed`: the
             reviewer blocked the PR and an agent pushed a fix).
  floors     each deterministic floor the article may name, with the check
             that runs it, whether that check is required on main, and the
             line in the repository's configuration that shows what it fails
             on. Nothing is a gate unless its check is required.

The pure functions below take plain values so tests/test_slop_measures.py pins
each count on fixed data; main() does the reading.
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys

UTC = dt.timezone.utc
PR_NUMBER = re.compile(r"\(#(\d+)\)\s*$")
REVERT = re.compile(r"^(?:Revert\b|revert[(:]|fix\(main-red\): revert #)")
MAIN_REPAIR = re.compile(r"^fix\(main-red\)")

# (floor, check, file in the repository, pattern whose match shows what fails)
FLOORS = (
    ("type check, untyped definitions disallowed", "mypy", "pyproject.toml",
     r"^disallow_untyped_defs = true$"),
    ("linter", "pre-commit", ".pre-commit-config.yaml", r"^\s*- id: ruff-check$"),
    ("coverage floor on changed lines", "test", "pyproject.toml", r"^fail_under = \d+$"),
    ("copy-paste detector", "jscpd", ".jscpd.json", r'^\s*"threshold": 0,$'),
    ("file-size cap", "audit-grep", ".github/workflows/audit-grep.yaml",
     r"Check no code or docs file grows past the line cap"),
    ("mutation score on changed lines", "changed-line-mutants",
     ".github/workflows/changed-line-mutants.yaml", r"never fails on one"),
)


def iso_week(ts):
    """The ISO week label of a UTC epoch, e.g. 2026-W41."""
    year, week, _ = dt.datetime.fromtimestamp(ts, UTC).isocalendar()
    return f"{year}-W{week:02d}"


def week_start(label):
    """The epoch of the Monday 00:00 UTC that opens ISO week `label`."""
    year, week = label.split("-W")
    return int(dt.datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=UTC).timestamp())


def week_labels(first_ts, last_ts):
    """Every ISO week label from the week of first_ts to the week of last_ts."""
    labels, ts = [], week_start(iso_week(first_ts))
    while ts <= last_ts:
        labels.append(iso_week(ts))
        ts += 7 * 86400
    return labels


def per_100(part, whole):
    return None if part is None or not whole else round(100.0 * part / whole, 2)


def parse_log(text):
    """[(epoch, subject)] from `git log --format=%ct%x09%s` output."""
    rows = []
    for line in text.splitlines():
        ts, _, subject = line.partition("\t")
        if ts.strip():
            rows.append((int(ts), subject))
    return rows


def merged_prs(commits):
    """[(epoch, pr number, subject)] for each commit that merged a PR."""
    out = []
    for ts, subject in commits:
        m = PR_NUMBER.search(subject)
        if m:
            out.append((ts, int(m.group(1)), subject))
    return out


def weekly(commits, now):
    """The `weeks` rows: merged PRs, reverts and main repairs per ISO week."""
    merges = merged_prs(commits)
    if not merges:
        return []
    repair_from = min((ts for ts, _, s in merges if MAIN_REPAIR.match(s)), default=None)
    first_repair_week = iso_week(repair_from) if repair_from is not None else None
    rows = []
    for label in week_labels(min(ts for ts, _, _ in merges), now):
        these = [s for ts, _, s in merges if iso_week(ts) == label]
        reverts = sum(1 for s in these if REVERT.match(s))
        counted = first_repair_week is not None and label >= first_repair_week
        repairs = sum(1 for s in these if MAIN_REPAIR.match(s) and not REVERT.match(s)) if counted else None
        rows.append({"week": label, "merged_prs": len(these), "reverts": reverts,
                     "reverts_per_100": per_100(reverts, len(these)), "main_repairs": repairs,
                     "main_repairs_per_100": per_100(repairs, len(these))})
    return rows


def _epoch(stamp):
    return int(dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp())


def red_weekly(spells, now):
    """The `red` rows from [(since, ended or None)] ISO stamps: hours red per week, spells begun, median minutes."""
    spans = [(_epoch(a), _epoch(b) if b else now) for a, b in spells]
    if not spans:
        return []
    rows = []
    for label in week_labels(min(a for a, _ in spans), now):
        lo, hi = week_start(label), week_start(label) + 7 * 86400
        seconds = sum(max(0, min(b, hi) - max(a, lo)) for a, b in spans)
        begun = [b - a for a, b in spans if lo <= a < hi]
        rows.append({"week": label, "hours_red": round(seconds / 3600.0, 1), "spells": len(begun),
                     "median_red_to_green_minutes": round(statistics.median(begun) / 60.0) if begun else None})
    return rows


def rounds_weekly(commits, fix_rounds, log_start, now):
    """The `rounds` rows: per ISO week that opens after log_start, merged PRs and the fix rounds pushed to them.

    fix_rounds is {pr number: rounds}. A week the job log does not cover from its Monday is left out: a PR merged
    in it may have had rounds before the log began."""
    rows = []
    merges = merged_prs(commits)
    for label in week_labels(log_start, now):
        if week_start(label) < log_start:
            continue
        numbers = [n for ts, n, _ in merges if iso_week(ts) == label]
        rounds = sum(fix_rounds.get(n, 0) for n in numbers)
        rows.append({"week": label, "merged_prs": len(numbers), "fix_rounds": rounds,
                     "fix_rounds_per_pr": round(rounds / len(numbers), 2) if numbers else None})
    return rows


def floors(required, read_file):
    """One row per floor: its check, whether the check is required, and the configuration line that shows it."""
    rows = []
    for name, check, path, pattern in FLOORS:
        text = read_file(path)
        m = re.search(pattern, text or "", re.M)
        is_required = check in required
        rows.append({"floor": name, "check": check, "required": is_required, "evidence": path,
                     "evidence_line": m.group(0).strip() if m else None,
                     "fails_the_pr": bool(is_required and m)})
    return rows


def _run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-dir", required=True, help="a clone of the main repository, fetched")
    ap.add_argument("--repo", required=True, help="its owner/name, for the required-check read")
    ap.add_argument("--work-db", required=True, help="the fleet's work.db (opened read-only)")
    ap.add_argument("--since", default="2026-04-01")
    ap.add_argument("--branch", default="origin/main")
    ap.add_argument("--out", default="data/slop_measures.json")
    a = ap.parse_args(argv)
    now = int(dt.datetime.now(UTC).timestamp())

    head = _run(["git", "rev-parse", a.branch], a.repo_dir).strip()
    commits = parse_log(_run(["git", "log", a.branch, "--first-parent", f"--since={a.since}",
                              "--format=%ct%x09%s"], a.repo_dir))
    db = sqlite3.connect(f"file:{a.work_db}?mode=ro", uri=True)
    spells = db.execute("select since, ended from red_spell where repo = ?", (a.repo,)).fetchall()
    log_start = db.execute("select min(created) from job where repo = ?", (a.repo,)).fetchone()[0]
    fix_rounds = dict(db.execute("select number, count(*) from job where repo = ? and kind = 'fix' "
                                 "and state = 'done' and outcome = 'pushed' group by number", (a.repo,)))
    required = set(json.loads(_run(["gh", "api", f"repos/{a.repo}/branches/main/protection/required_status_checks",
                                    "--jq", ".contexts"])))

    def read_file(path):
        try:
            return _run(["git", "show", f"{head}:{path}"], a.repo_dir)
        except subprocess.CalledProcessError:
            return None

    out = {
        "measured_at": dt.datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "main_head": head,
        "command": "python3 scripts/slop_measures.py --repo-dir <clone of the main repository> "
                   "--repo <its owner/name> --work-db <the fleet's work.db> --since " + a.since,
        "definitions": "the docstring of scripts/slop_measures.py",
        "weeks": weekly(commits, now),
        "red": red_weekly(spells, now),
        "rounds": rounds_weekly(commits, fix_rounds, _epoch(log_start), now) if log_start else [],
        "floors": floors(required, read_file),
        "unmeasured": {
            "whole_suite_coverage": "the PR-side test job applies the floor to changed lines only and says the "
                                    "whole-suite floor runs post-merge; its total is not read here yet",
            "real_share_of_review_findings": "the job log records that a fix was pushed, not whether each finding "
                                             "was real",
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {a.out}: {len(out['weeks'])} weeks, {len(out['red'])} red weeks, "
          f"{len(out['rounds'])} round weeks, {len(out['floors'])} floors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
