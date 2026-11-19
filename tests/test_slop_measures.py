"""Pins each count scripts/slop_measures.py makes, on fixed data (issue #32, slice 1).

Run: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import slop_measures as sm  # noqa: E402

# Monday 2026-10-12 00:00 UTC opens ISO week 2026-W42.
W42 = 1791763200
DAY = 86400


def log(*rows):
    return "\n".join(f"{ts}\t{subject}" for ts, subject in rows) + "\n"


COMMITS = sm.parse_log(log(
    (W42 + 1 * DAY, "feat(engine): a thing (#10)"),
    (W42 + 2 * DAY, 'Revert "feat(engine): a thing (#10)" (#11)'),
    (W42 + 3 * DAY, "chore: a direct push with no PR number"),
    (W42 + 7 * DAY + 1, "fix(main-red): the test reads the new key (#12) (#13)"),
    (W42 + 7 * DAY + 2, "fix(main-red): revert #13 (#14)"),
    (W42 + 7 * DAY + 3, "revert(config): restore the old type (#15)"),
    (W42 + 7 * DAY + 4, "docs: a page (#16)"),
    (W42 + 7 * DAY + 5, "feat(studio): a panel (#17)"),
))


class WeeklyTest(unittest.TestCase):
    def test_counts_merges_reverts_and_main_repairs_per_iso_week(self):
        rows = sm.weekly(COMMITS, now=W42 + 8 * DAY)
        self.assertEqual(rows, [
            {"week": "2026-W42", "merged_prs": 2, "reverts": 1, "reverts_per_100": 50.0,
             "main_repairs": None, "main_repairs_per_100": None},
            {"week": "2026-W43", "merged_prs": 5, "reverts": 2, "reverts_per_100": 40.0,
             "main_repairs": 1, "main_repairs_per_100": 20.0},
        ])

    def test_an_empty_week_between_merges_reads_zero_merges(self):
        commits = sm.parse_log(log((W42, "a (#1)"), (W42 + 14 * DAY, "b (#2)")))
        rows = sm.weekly(commits, now=W42 + 14 * DAY)
        self.assertEqual([r["merged_prs"] for r in rows], [1, 0, 1])
        self.assertIsNone(rows[1]["reverts_per_100"])


class RedTest(unittest.TestCase):
    def test_hours_are_split_at_the_week_boundary_and_an_open_spell_runs_to_now(self):
        spells = [
            ("2026-10-18T23:00:00Z", "2026-10-19T01:00:00Z"),  # Sunday 23:00 to Monday 01:00: 1 h each side
            ("2026-10-20T10:00:00Z", "2026-10-20T10:30:00Z"),
            ("2026-10-21T12:00:00Z", None),
        ]
        now = sm._epoch("2026-10-21T15:00:00Z")
        self.assertEqual(sm.red_weekly(spells, now), [
            {"week": "2026-W42", "hours_red": 1.0, "spells": 1, "median_red_to_green_minutes": 120},
            {"week": "2026-W43", "hours_red": 4.5, "spells": 2, "median_red_to_green_minutes": 105},
        ])


class RoundsTest(unittest.TestCase):
    def test_a_week_the_log_does_not_cover_from_its_monday_is_left_out(self):
        log_start = W42 + 1 * DAY
        rows = sm.rounds_weekly(COMMITS, {10: 3, 13: 1, 17: 2, 99: 5}, log_start, now=W42 + 8 * DAY)
        self.assertEqual(rows, [{"week": "2026-W43", "merged_prs": 5, "fix_rounds": 3, "fix_rounds_per_pr": 0.6}])


class FloorsTest(unittest.TestCase):
    FILES = {
        "pyproject.toml": "[tool.mypy]\ndisallow_untyped_defs = true\n[tool.coverage.report]\nfail_under = 60\n",
        ".pre-commit-config.yaml": "repos:\n  - hooks:\n      - id: ruff-check\n",
        ".jscpd.json": '{\n  "threshold": 0,\n}\n',
        ".github/workflows/changed-line-mutants.yaml": "# lists each survivor and never fails on one.\n",
    }

    def test_a_floor_fails_the_pr_only_when_its_check_is_required_and_its_line_is_there(self):
        rows = {r["check"]: r for r in sm.floors({"mypy", "test", "jscpd", "audit-grep"}, self.FILES.get)}
        self.assertTrue(rows["mypy"]["fails_the_pr"])
        self.assertEqual(rows["test"]["evidence_line"], "fail_under = 60")
        self.assertTrue(rows["jscpd"]["fails_the_pr"])
        # Required, but its configuration line is absent: not called a gate.
        self.assertFalse(rows["audit-grep"]["fails_the_pr"])
        # Its line is there, but the check is not required: advisory.
        self.assertFalse(rows["pre-commit"]["fails_the_pr"])
        self.assertEqual(rows["changed-line-mutants"]["evidence_line"], "never fails on one")
        self.assertFalse(rows["changed-line-mutants"]["fails_the_pr"])


if __name__ == "__main__":
    unittest.main()
