#!/usr/bin/env python3
"""Generate deterministic synthetic review data with planted problems.

Stdlib only. Writes CSVs, an ingest-shaped seed.json, triage.json and expected_flags.json
to backend/data/, then verifies that exactly the planted problems are detectable by the
flag rules (independent re-implementation, not the production engine).

    python backend/scripts/generate_synthetic_data.py
"""
import csv
import json
import math
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260720
START = datetime(2026, 7, 20, tzinfo=timezone.utc)          # Monday, week 1
AS_OF = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)   # Friday evening, end of week 12
WEEKS = 12
OUT = Path(__file__).resolve().parents[1] / "data"

rng = random.Random(SEED)

DEVS = [
    (1, "Maya Chen", "mchen", "manager"),
    (2, "Arjun Rao", "arao", "dev"),
    (3, "Lena Fischer", "lfischer", "dev"),
    (4, "Omar Haddad", "ohaddad", "dev"),
    (5, "Priya Nair", "pnair", "dev"),
    (6, "Tomás Silva", "tsilva", "dev"),
    (7, "Jin Park", "jpark", "dev"),
    (8, "Chloe Dubois", "cdubois", "dev"),
]
MANAGER, ARJUN, LENA, OMAR, PRIYA, TOMAS, JIN, CHLOE = 1, 2, 3, 4, 5, 6, 7, 8
DEV_IDS = [d[0] for d in DEVS if d[3] == "dev"]
NAME = {d[0]: d[1] for d in DEVS}

WEEKLY_PRS = [13, 14, 16, 18, 19, 20, 21, 23, 24, 25, 26, 27]  # volume ramps up (framing: more code, same reviewers)

SCOPES = ["billing", "auth", "search", "notifications", "export", "onboarding", "api", "dashboard",
          "reports", "cache", "webhooks", "settings", "audit-log", "scheduler", "uploads"]
ACTIONS = ["add pagination to {}", "handle empty state in {}", "cache lookups for {}", "validate input for {}",
           "retry failed calls in {}", "split {} into smaller modules", "add metrics to {}",
           "fix timezone handling in {}", "support bulk edits in {}", "tighten permissions for {}",
           "speed up queries in {}", "migrate {} to the new client", "improve error messages in {}",
           "add feature flag for {}", "remove dead code from {}"]
PREFIX = ["feat", "fix", "refactor", "perf", "chore"]

SUBSTANTIVE = [
    "This query runs inside the loop, so it issues one SELECT per row. Can we batch it with an IN clause?",
    "If the upstream call times out here we swallow the exception and return an empty list. Should this surface an error?",
    "The new helper duplicates the retry logic in the client module. Could we reuse that instead of adding a second backoff?",
    "Nothing covers the case where the token is expired but the refresh succeeds. Worth a test before this merges.",
    "This mutates the shared config dict, so concurrent requests could see each other's overrides. Please copy it first.",
    "Naming nit with a real consequence: `status` here means HTTP status but later it means job status. Rename one of them.",
    "The migration drops the column in the same release that stops writing it. Safer to split into two deploys.",
    "We compare datetimes without a timezone here, which breaks across the DST boundary. Use aware datetimes.",
    "Does this need to be public? Keeping it private avoids a second caller depending on the ordering quirk.",
    "The index on (account_id, created_at) will not help this filter because of the OR. Can we rewrite as a UNION?",
    "On failure we log the full request body, which includes the customer email. Please redact before logging.",
    "The loop recomputes the total on every iteration. Hoist it out, it is O(n^2) for large invoices.",
    "I think the off-by-one here drops the last page of results when the count is an exact multiple of the page size.",
    "This catch block is too broad and will hide programming errors. Catch the specific exception type instead.",
    "Could we add a comment on why 30 seconds? It looks arbitrary, and the SLA doc says 45.",
    "The feature flag default is true in this file but false in the config service, so staging will differ from prod.",
    "Returning a mutable default argument here means state leaks between calls. Use None and build it inside.",
    "Good approach overall. One concern: the lock is released before the write completes, so two workers can interleave.",
    "This test only asserts the status code. Please also assert the response body so a wrong payload fails the test.",
    "Cache key is missing the tenant id, so one tenant could be served another tenant's cached result.",
]
SHORT_NOISE = ["LGTM", "+1", "👍", "Looks good!", "ship it", "approved", "nit"]

counters = {"pr": 0}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def bump_weekday(dt):
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt


def rand_dt_in_week(week):
    day = rng.choices([0, 1, 2, 3, 4], [1.0, 1.2, 1.2, 1.1, 0.8])[0]
    return (START + timedelta(weeks=week - 1, days=day, hours=rng.randrange(8, 18),
                              minutes=rng.randrange(60), seconds=rng.randrange(60)))


def make_title():
    return "%s(%s): %s" % (rng.choice(PREFIX), rng.choice(SCOPES),
                           rng.choice(ACTIONS).format(rng.choice(SCOPES)))


def size_split(lines):
    adds = int(lines * rng.uniform(0.6, 0.85))
    return adds, lines - adds


def new_spec(week, opened, author, lines, title=None, kind="normal"):
    adds, dels = size_split(lines)
    return {"week": week, "opened": opened, "author": author, "adds": adds, "dels": dels,
            "title": title or make_title(), "kind": kind, "scn": "base", "fixes": None,
            "reviews": [], "requests": [], "merged_at": None, "merged_by": None, "no_clip": False}


def lines_of(s):
    return s["adds"] + s["dels"]


def set_lines(s, lines):
    s["adds"], s["dels"] = size_split(lines)


# ---------------------------------------------------------------- review building blocks
def sub_comments(t0, t, n):
    out = []
    for body in rng.sample(SUBSTANTIVE, n):
        ct = max(t0 + timedelta(minutes=1), t - timedelta(minutes=rng.uniform(1, 25)))
        out.append((body, True, ct))
    return out


def add_review(s, reviewer, state, t, comments):
    s["reviews"].append({"reviewer": reviewer, "state": state, "t": t, "comments": comments})


def approval_comments(s, reviewer, t, reapproval=False):
    lines = lines_of(s)
    if reapproval:
        n = 1 if lines >= 300 else rng.choice([0, 0, 1])
    elif lines >= 300:
        n = rng.randint(2, 5)
    elif lines >= 100:
        n = rng.randint(1, 3) if rng.random() < 0.8 else 0
    else:
        n = rng.randint(0, 2) if rng.random() < 0.6 else 0
    if reviewer == ARJUN and s["week"] >= 7:      # stretched thin: fewer comments late in the period
        n = max(1 if lines >= 300 else 0, n - 1)
    cs = sub_comments(s["opened"], t, n)
    if rng.random() < 0.3:
        cs.append((rng.choice(["Looks good!", "LGTM", "👍"]), False, t - timedelta(seconds=rng.randint(5, 60))))
    return cs


def first_delay_minutes(reviewer, week, lines):
    median = 150 + week * 30 if reviewer == ARJUN else 180
    d = rng.lognormvariate(math.log(median), 0.8)
    return min(max(d, 15, lines * 0.5), 36 * 60)


def pick_reviewers(author, lines, week):
    cands = [d for d in DEV_IDS if d != author and not (lines >= 300 and d == OMAR)]
    w = {d: 1.0 for d in cands}
    w[OMAR] = 0.7
    w[ARJUN] = 8 + 2 * week
    k = 2 if (lines >= 250 or rng.random() < 0.2) else 1
    chosen = []
    for _ in range(k):
        pool = [d for d in cands if d not in chosen]
        chosen.append(rng.choices(pool, [w[d] for d in pool])[0])
    return chosen


def pick_merger(s, approvers):
    r = rng.random()
    if r < 0.78:
        return s["author"]
    if r < 0.85:
        return MANAGER
    return rng.choice(approvers)


def build_base(s, reviewers=None):
    t0, lines = s["opened"], lines_of(s)
    reviewers = reviewers or pick_reviewers(s["author"], lines, s["week"])
    finals = []
    for r in reviewers:
        t = t0 + timedelta(minutes=first_delay_minutes(r, s["week"], lines))
        if rng.random() < 0.18:
            add_review(s, r, "changes_requested", t, sub_comments(t0, t, rng.randint(2, 4)))
            t2 = t + timedelta(minutes=rng.uniform(120, 1200))
            add_review(s, r, "approved", t2, approval_comments(s, r, t2, reapproval=True))
            finals.append(t2)
        else:
            add_review(s, r, "approved", t, approval_comments(s, r, t))
            finals.append(t)
        s["requests"].append({"reviewer": r, "requested": t0, "fulfilled": t})
    s["merged_at"] = max(finals) + timedelta(minutes=rng.uniform(30, 480))
    s["merged_by"] = pick_merger(s, reviewers)


# ---------------------------------------------------------------- planted scenarios
def build_stamp(s, reviewer):
    set_lines(s, rng.randint(320, 900))
    t = s["opened"] + timedelta(seconds=rng.randint(35, 110))
    cs = [("LGTM", False, t - timedelta(seconds=3))] if rng.random() < 0.4 else []
    add_review(s, reviewer, "approved", t, cs)
    s["requests"].append({"reviewer": reviewer, "requested": s["opened"], "fulfilled": t})
    s["merged_at"] = t + timedelta(minutes=rng.uniform(20, 180))
    s["merged_by"] = s["author"]
    s["scn"] = "rubber_stamp"


def build_self_approval(s):
    s["author"] = JIN
    set_lines(s, rng.randint(25, 120))
    t = s["opened"] + timedelta(minutes=rng.uniform(5, 25))
    add_review(s, JIN, "approved", t, [])
    s["merged_at"] = t + timedelta(minutes=rng.uniform(2, 30))
    s["merged_by"] = JIN
    s["scn"] = "self_approval"


def build_unreviewed(s, author):
    s["author"] = author
    set_lines(s, rng.randint(5, 45))
    s["title"] = "chore(%s): %s" % (rng.choice(SCOPES), rng.choice(["bump config values", "update copy", "adjust timeout",
                                                                      "rename env var", "tweak log level"]))
    s["merged_at"] = s["opened"] + timedelta(minutes=rng.uniform(3, 40))
    s["merged_by"] = author
    s["scn"] = "merged_unreviewed"


def build_changes_pending(s):
    s["author"] = TOMAS
    set_lines(s, rng.randint(120, 220))
    t0 = s["opened"]
    t_l = t0 + timedelta(hours=5)
    t_p = t0 + timedelta(hours=4)
    add_review(s, PRIYA, "approved", t_p, sub_comments(t0, t_p, 1))
    add_review(s, LENA, "changes_requested", t_l, sub_comments(t0, t_l, 3))
    s["requests"] += [{"reviewer": PRIYA, "requested": t0, "fulfilled": t_p},
                      {"reviewer": LENA, "requested": t0, "fulfilled": t_l}]
    s["merged_at"] = t0 + timedelta(hours=9)
    s["merged_by"] = TOMAS
    s["scn"] = "merged_changes_pending"


def build_arjun_only(s):
    set_lines(s, rng.randint(160, 280))
    build_base(s, reviewers=[ARJUN])
    s["scn"] = "escape_target"


def build_fix(orig, kind, author, reviewer):
    if reviewer == author:
        reviewer = next(d for d in (LENA, PRIYA, TOMAS, CHLOE) if d != author)
    opened = bump_weekday(orig["merged_at"] + timedelta(days=rng.uniform(3, 7)))
    title = ('Revert "%s"' % orig["title"]) if kind == "revert" else "hotfix(%s): %s" % (
        rng.choice(SCOPES), rng.choice(["guard null result", "restore previous timeout", "correct off-by-one",
                                         "stop duplicate emails"]))
    s = new_spec(0, opened, author, 20, title=title, kind=kind)
    set_lines(s, rng.randint(20, 150) if kind == "revert" else rng.randint(8, 60))
    s["fixes"] = orig
    s["scn"] = "fix"
    t = opened + timedelta(minutes=rng.uniform(10, 45))
    add_review(s, reviewer, "approved", t, sub_comments(opened, t, rng.choice([0, 1])))
    s["requests"].append({"reviewer": reviewer, "requested": opened, "fulfilled": t})
    s["merged_at"] = t + timedelta(minutes=rng.uniform(10, 60))
    s["merged_by"] = author
    return s


def build_stale_open(opened, author, other):
    s = new_spec(12, opened, author, rng.randint(80, 250))
    s["scn"] = "stale_open"
    s["no_clip"] = True
    t = opened + timedelta(hours=rng.uniform(2, 6))
    add_review(s, other, "approved", t, sub_comments(opened, t, rng.randint(1, 2)))
    s["requests"] += [{"reviewer": other, "requested": opened, "fulfilled": t},
                      {"reviewer": ARJUN, "requested": opened, "fulfilled": None}]
    return s


def generate():
    specs = []
    for week, n in enumerate(WEEKLY_PRS, start=1):
        for _ in range(n):
            author = rng.choices(DEV_IDS, [0.6 if d == ARJUN else 1.1 for d in DEV_IDS])[0]
            lines = int(min(max(rng.lognormvariate(4.3, 0.9), 4), 1200))
            specs.append(new_spec(week, rand_dt_in_week(week), author, lines))

    def take(week, pred=lambda s: True):
        pool = [s for s in specs if s["week"] == week and s["scn"] == "base" and pred(s)]
        s = rng.choice(pool)
        s["scn"] = "taken"
        return s

    def non_omar(s):
        return s["author"] not in (OMAR, JIN)

    # rubber-stamp pattern for Omar (weeks 9-12 fall inside the 30-day window); one-off for Jin
    stamps = {}
    for wk in (2, 4, 6, 9, 10, 11, 12):
        s = take(wk, non_omar)
        build_stamp(s, OMAR)
        stamps[wk] = s
    jin_stamp = take(7, lambda s: s["author"] not in (JIN, OMAR))
    build_stamp(jin_stamp, JIN)

    # self-approval pattern for Jin, both inside the 14-day window
    for wk in (11, 12):
        s = take(wk)
        build_self_approval(s)

    # unreviewed merges, spread out
    for wk, author in ((3, TOMAS), (5, CHLOE), (7, PRIYA), (11, LENA), (12, TOMAS)):
        build_unreviewed(take(wk, lambda s, a=author: s["author"] != a or True), author)

    build_changes_pending(take(8))

    e2 = take(9, lambda s: s["author"] not in (ARJUN, OMAR))
    build_arjun_only(e2)

    # base reviews for everything else
    for s in specs:
        if s["scn"] == "base":
            build_base(s)

    # escapes: fix PRs that explicitly point at the original
    fixes = [
        build_fix(stamps[6], "hotfix", CHLOE if stamps[6]["author"] != CHLOE else PRIYA, LENA),
        build_fix(e2, "revert", e2["author"], PRIYA),
        build_fix(stamps[10], "hotfix", LENA if stamps[10]["author"] != LENA else CHLOE, ARJUN),
    ]
    # open PRs waiting on Arjun: two stale (> 48h), two recent
    stale = [
        build_stale_open(datetime(2026, 10, 2, 10, 20, tzinfo=timezone.utc), LENA, PRIYA),
        build_stale_open(datetime(2026, 10, 6, 14, 5, tzinfo=timezone.utc), CHLOE, TOMAS),
        build_stale_open(datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc), PRIYA, JIN),
        build_stale_open(datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc), TOMAS, LENA),
    ]
    return specs + fixes + stale


def clip_to_as_of(specs):
    for s in specs:
        if s["no_clip"]:
            continue
        s["reviews"] = [r for r in s["reviews"] if r["t"] <= AS_OF]
        for r in s["reviews"]:
            r["comments"] = [c for c in r["comments"] if c[2] <= AS_OF]
        done = {}
        for r in s["reviews"]:
            done.setdefault(r["reviewer"], r["t"])
        for q in s["requests"]:
            q["fulfilled"] = done.get(q["reviewer"]) if q["fulfilled"] and q["fulfilled"] <= AS_OF else None
        if s["merged_at"] and s["merged_at"] > AS_OF:
            s["merged_at"] = s["merged_by"] = None


def flatten(specs):
    specs = sorted(specs, key=lambda s: s["opened"])
    for i, s in enumerate(specs, start=1):
        s["id"] = i
    prs, reviews, comments, requests = [], [], [], []
    for s in specs:
        prs.append({"id": s["id"], "title": s["title"], "author_id": s["author"],
                    "merged_by_id": s["merged_by"], "opened_at": s["opened"], "merged_at": s["merged_at"],
                    "additions": s["adds"], "deletions": s["dels"],
                    "fixes_pr_id": s["fixes"]["id"] if s["fixes"] else None, "kind": s["kind"]})
        for r in s["reviews"]:
            reviews.append({"pr_id": s["id"], "reviewer_id": r["reviewer"], "state": r["state"],
                            "submitted_at": r["t"], "_c": r["comments"]})
        for q in s["requests"]:
            requests.append({"pr_id": s["id"], "reviewer_id": q["reviewer"], "requested_at": q["requested"],
                             "fulfilled_at": q["fulfilled"]})
    reviews.sort(key=lambda r: (r["submitted_at"], r["pr_id"]))
    for i, r in enumerate(reviews, start=1):
        r["id"] = i
        for body, is_line, ct in sorted(r["_c"], key=lambda c: c[2]):
            comments.append({"review_id": i, "body": body, "is_line_comment": is_line, "created_at": ct})
    for r in reviews:
        del r["_c"]
    comments.sort(key=lambda c: (c["created_at"], c["review_id"]))
    for i, c in enumerate(comments, start=1):
        c["id"] = i
    requests.sort(key=lambda q: (q["requested_at"], q["pr_id"], q["reviewer_id"]))
    for i, q in enumerate(requests, start=1):
        q["id"] = i
    return prs, reviews, comments, requests


# ---------------------------------------------------------------- independent verifier (flag rules)
STOP = {"lgtm", "nit", "+1", "approved", "ship it", "looks good", "👍"}
DISMISSED_KEY = ("rubber_stamp", "dismissed")


def substantive(c):
    b = c["body"].strip()
    return len(b) >= 30 and c["is_line_comment"] and b.lower().strip("!. ") not in STOP


def compute_flags(prs, reviews, comments, requests, dismissed=()):
    P = {p["id"]: p for p in prs}
    by_pr, by_rev = {}, {}
    for r in reviews:
        by_pr.setdefault(r["pr_id"], []).append(r)
    for c in comments:
        by_rev.setdefault(c["review_id"], []).append(c)
    flags = []

    def add(rule, pr_id, person, role, t, **ev):
        flags.append({"rule_key": rule, "pr_id": pr_id, "person_id": person, "role": role,
                      "t": t, "evidence": ev})

    for p in prs:
        rs = sorted(by_pr.get(p["id"], []), key=lambda r: r["submitted_at"])
        lines = p["additions"] + p["deletions"]
        if p["merged_at"]:
            if not [r for r in rs if r["submitted_at"] <= p["merged_at"]]:
                add("merged_unreviewed", p["id"], p["author_id"], "author", p["merged_at"], lines=lines)
            latest = {}
            for r in rs:
                if r["submitted_at"] <= p["merged_at"]:
                    latest[r["reviewer_id"]] = r["state"]
            if "changes_requested" in latest.values():
                add("merged_changes_pending", p["id"], p["author_id"], "author", p["merged_at"])
        approvers = {r["reviewer_id"] for r in rs if r["state"] == "approved"}
        if approvers and approvers == {p["author_id"]}:
            add("self_approval", p["id"], p["author_id"], "author", p["merged_at"] or p["opened_at"])
        for r in rs:
            if r["state"] != "approved" or lines < 300:
                continue
            secs = (r["submitted_at"] - p["opened_at"]).total_seconds()
            subs = [c for c in by_rev.get(r["id"], []) if substantive(c)]
            if secs < 120 or not subs:
                add("rubber_stamp", p["id"], r["reviewer_id"], "reviewer", r["submitted_at"],
                    lines=lines, seconds_to_approve=int(secs), substantive_comments=len(subs))
        if approvers and p["merged_at"]:
            for q in prs:
                if q["fixes_pr_id"] == p["id"] and timedelta(0) < q["opened_at"] - p["merged_at"] <= timedelta(days=14):
                    for a in sorted(approvers):
                        add("escape", p["id"], a, "reviewer", q["opened_at"], fix_pr_id=q["id"], kind=q["kind"])
    for q in requests:
        if q["fulfilled_at"] is None and (AS_OF - q["requested_at"]) > timedelta(hours=48):
            add("stale_backlog", q["pr_id"], q["reviewer_id"], "reviewer", q["requested_at"],
                waiting_hours=round((AS_OF - q["requested_at"]).total_seconds() / 3600, 1))

    # load concentration over the last 28 days
    since = AS_OF - timedelta(days=28)
    counts = {d: 0 for d in DEV_IDS}
    for r in reviews:
        if r["submitted_at"] >= since and r["reviewer_id"] in counts:
            counts[r["reviewer_id"]] += 1
    total = sum(counts.values()) or 1
    top2 = sum(sorted(counts.values(), reverse=True)[:2]) / total
    med = statistics.median(counts.values())
    heavy = [d for d, n in counts.items() if med and n > 2 * med]
    load = {"counts": counts, "top2_share": round(top2, 3), "median": med, "over_2x_median": heavy}
    if top2 > 0.6 or heavy:
        add("load_concentration", None, None, None, AS_OF, **load)

    # repeat patterns over non-dismissed flags
    live = [f for f in flags if (f["rule_key"], f["pr_id"], f["person_id"], f["role"]) not in dismissed
            and f["person_id"] is not None]
    groups = {}
    for f in live:
        groups.setdefault((f["person_id"], f["role"], f["rule_key"]), []).append(f)
    patterns = []
    for (person, role, rule), fs in groups.items():
        window, need = (14, 2) if rule == "self_approval" else (30, 3)
        inside = [f for f in fs if AS_OF - f["t"] <= timedelta(days=window)]
        if len(inside) >= need:
            patterns.append({"person_id": person, "role": role, "rule_key": rule, "window_days": window,
                             "count": len(inside), "pr_ids": sorted(f["pr_id"] for f in inside)})
    return flags, patterns, load


def main():
    specs = generate()
    clip_to_as_of(specs)
    prs, reviews, comments, requests = flatten(specs)

    # triage the demo should start with (flags are produced by the engine; these are applied afterwards)
    stamp_flags_omar = sorted(
        [p for p in prs if p["author_id"] != OMAR and any(
            r["pr_id"] == p["id"] and r["reviewer_id"] == OMAR for r in reviews) and p["additions"] + p["deletions"] >= 300],
        key=lambda p: p["opened_at"])
    wk9_pr = [p for p in stamp_flags_omar if datetime(2026, 9, 14, tzinfo=timezone.utc) <= p["opened_at"] < datetime(2026, 9, 21, tzinfo=timezone.utc)][0]
    first_escape_flags, _, _ = compute_flags(prs, reviews, comments, requests)
    unrev_priya = [f for f in first_escape_flags if f["rule_key"] == "merged_unreviewed" and f["person_id"] == PRIYA][0]
    esc_first = sorted([f for f in first_escape_flags if f["rule_key"] == "escape"], key=lambda f: f["t"])[0]
    triage = [
        {"rule_key": "rubber_stamp", "pr_id": wk9_pr["id"], "person_id": OMAR, "role": "reviewer",
         "status": "dismissed", "dismiss_reason": "Live pairing session: author and reviewer walked through the diff together."},
        {"rule_key": "merged_unreviewed", "pr_id": unrev_priya["pr_id"], "person_id": PRIYA, "role": "author",
         "status": "acknowledged", "note": "Config-only change agreed in standup."},
        {"rule_key": "escape", "pr_id": esc_first["pr_id"], "person_id": esc_first["person_id"], "role": "reviewer",
         "status": "acknowledged", "note": "To raise in the next retro."},
    ]
    dismissed = {(t["rule_key"], t["pr_id"], t["person_id"], t["role"]) for t in triage if t["status"] == "dismissed"}
    flags, patterns, load = compute_flags(prs, reviews, comments, requests, dismissed)

    # ---- sanity checks on the planted problems
    tally = {}
    for f in flags:
        tally[f["rule_key"]] = tally.get(f["rule_key"], 0) + 1
    expected = {"rubber_stamp": 8, "self_approval": 2, "merged_unreviewed": 5, "merged_changes_pending": 1,
                "escape": 3, "stale_backlog": 2, "load_concentration": 1}
    problems = []
    if tally != expected:
        problems.append("flag tally %s != expected %s" % (tally, expected))
    want_patterns = {(OMAR, "reviewer", "rubber_stamp"), (JIN, "author", "self_approval")}
    got_patterns = {(p["person_id"], p["role"], p["rule_key"]) for p in patterns}
    if got_patterns != want_patterns:
        problems.append("patterns %s != expected %s" % (got_patterns, want_patterns))
    rev_counts = {}
    for r in reviews:
        rev_counts[r["reviewer_id"]] = rev_counts.get(r["reviewer_id"], 0) + 1
    arjun_share = rev_counts[ARJUN] / len(reviews)
    if arjun_share < 0.55:
        problems.append("Arjun share %.2f below 0.55" % arjun_share)
    if problems:
        print("VERIFICATION FAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)

    # ---- write files
    OUT.mkdir(parents=True, exist_ok=True)

    def fmt(v):
        if isinstance(v, datetime):
            return iso(v)
        if isinstance(v, bool):
            return "true" if v else "false"
        return "" if v is None else v

    def write_csv(name, rows, cols):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for row in rows:
                w.writerow([fmt(row[c]) for c in cols])

    dev_rows = [{"id": d[0], "name": d[1], "handle": d[2], "role": d[3]} for d in DEVS]
    write_csv("developers.csv", dev_rows, ["id", "name", "handle", "role"])
    write_csv("pull_requests.csv", prs, ["id", "title", "author_id", "merged_by_id", "opened_at", "merged_at",
                                         "additions", "deletions", "fixes_pr_id", "kind"])
    write_csv("reviews.csv", reviews, ["id", "pr_id", "reviewer_id", "state", "submitted_at"])
    write_csv("review_comments.csv", comments, ["id", "review_id", "body", "is_line_comment", "created_at"])
    write_csv("review_requests.csv", requests, ["id", "pr_id", "reviewer_id", "requested_at", "fulfilled_at"])

    def jsonable(rows):
        return [{k: (iso(v) if isinstance(v, datetime) else v) for k, v in r.items()} for r in rows]

    seed = {"as_of": iso(AS_OF), "developers": dev_rows, "pull_requests": jsonable(prs),
            "reviews": jsonable(reviews), "review_comments": jsonable(comments),
            "review_requests": jsonable(requests)}
    (OUT / "seed.json").write_text(json.dumps(seed, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "triage.json").write_text(json.dumps(triage, ensure_ascii=False, indent=1), encoding="utf-8")
    exp = {"as_of": iso(AS_OF), "flag_counts": tally, "load": load,
           "flags": [{"rule_key": f["rule_key"], "pr_id": f["pr_id"], "person_id": f["person_id"], "role": f["role"],
                      "evidence": f["evidence"]} for f in sorted(flags, key=lambda f: (f["rule_key"], f["pr_id"] or 0))],
           "repeat_patterns": patterns}
    (OUT / "expected_flags.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- summary
    print("developers %d, PRs %d (merged %d, open %d), reviews %d, comments %d, requests %d" % (
        len(dev_rows), len(prs), sum(1 for p in prs if p["merged_at"]), sum(1 for p in prs if not p["merged_at"]),
        len(reviews), len(comments), len(requests)))
    print("reviews by person:", {NAME[k]: v for k, v in sorted(rev_counts.items(), key=lambda kv: -kv[1])})
    print("Arjun share of all reviews: %.0f%%" % (arjun_share * 100))
    print("flags:", tally)
    print("patterns:", [(NAME[p["person_id"]], p["rule_key"], p["count"]) for p in patterns])
    print("load:", load)


if __name__ == "__main__":
    main()
