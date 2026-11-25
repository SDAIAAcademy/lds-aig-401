# /// script
# requires-python = ">=3.10"
# ///
"""Recompute every number of the reference solutions from labs/files/ and check it.

    uv run labs/solutions/check.py            # every lab and the slide examples
    uv run labs/solutions/check.py 1.1 3.2    # some of them

Standard library only. Nothing here calls a model and nothing is written to disk. Each lab prints what it
computed and PASS, or stops at the first difference from the reference values in the solution files.
"""
from __future__ import annotations

import csv
import statistics as st
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = HERE.parent / "files"
LABS: dict[str, callable] = {}
READING = (2026, 10)
GENAI_WORDS = ("توليدي", "نموذج لغوي")


def lab(i):
    def wrap(fn):
        LABS[i] = fn
        return fn
    return wrap


def rows(name):
    with open(FILES / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def eq(label, got, want):
    if got != want:
        raise SystemExit(f"FAIL {label}: got {got!r}, want {want!r}")
    print(f"  {label}: {got}")


def months_since(ym: str) -> int:
    y, m = map(int, ym.split("-"))
    return (READING[0] - y) * 12 + READING[1] - m


def band(level) -> int:
    if level == "":
        return 0
    v = int(level)
    return 1 if v <= 2 else 2 if v <= 6 else 3 if v <= 12 else 4


def exposure(r) -> int:
    """Course rule: an unassessed system that affects people counts as high, otherwise as medium."""
    if r["risk_level"] == "":
        return 3 if r["affects_people"] == "نعم" else 2
    return band(r["risk_level"])


def is_genai(r) -> bool:
    return r["kind"] in ("مساعد توليدي", "وكيل") or any(w in r["function"] for w in GENAI_WORDS)


def workdays(a: date, b: date) -> int:
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() in (6, 0, 1, 2, 3):
            n += 1
    return n


def iso(s):
    return date.fromisoformat(s)


# ------------------------------------------------------------------ lab 1.1
def slice_facts():
    inv = [r for r in rows("inventory.csv") if r["unit"] in ("U1", "U2")]
    survey = [r for r in rows("staff_tools_survey.csv") if r["unit"] in ("U1", "U2")]
    unreg = [r for r in survey if r["in_register"] == "لا"]
    return inv, survey, unreg


@lab("1.1")
def lab_1_1():
    inv, survey, unreg = slice_facts()
    eq("systems in the slice", len(inv), 22)
    eq("agents", sorted(r["system_id"] for r in inv if r["kind"] == "وكيل"), ["SYS-04", "SYS-12", "SYS-21"])
    eq("unregistered AI tools found by the survey", sorted(r["tool_id"] for r in unreg), ["T-01", "T-02", "T-03"])
    eq("register coverage %", round(100 * len(inv) / (len(inv) + len(unreg))), 88)
    no_owner = sorted(r["system_id"] for r in inv if not r["owner_role"])
    eq("no owner", no_owner, ["SYS-04", "SYS-06", "SYS-14", "SYS-19"])
    unassessed = sorted(r["system_id"] for r in inv if r["risk_level"] == "")
    eq("never risk-assessed", unassessed, ["SYS-04", "SYS-06", "SYS-14", "SYS-19"])
    overdue = sorted(r["system_id"] for r in inv if r["last_review"] and months_since(r["last_review"]) > 12)
    eq("review overdue (more than 12 months)", overdue, ["SYS-02", "SYS-11", "SYS-13"])
    genai_hi = sorted(r["system_id"] for r in inv if is_genai(r) and r["data_class"] in ("مقيد", "سري"))
    genai_hi_tools = sorted(r["tool_id"] for r in unreg if any(w in r["description"] for w in GENAI_WORDS) and r["data_class"] != "عام")
    eq("GenAI over Public data, registered", genai_hi, ["SYS-04", "SYS-06", "SYS-14", "SYS-15", "SYS-21"])
    eq("GenAI over Public data, unregistered", genai_hi_tools, ["T-01", "T-02"])
    high_no_ia = sorted(r["system_id"] for r in inv if r["risk_level"] and int(r["risk_level"]) >= 8 and r["impact_assessment"] == "لا")
    eq("high level without impact assessment", high_no_ia, ["SYS-02"])
    decides_no_review = sorted(r["system_id"] for r in inv if r["decision_role"] == "يقرر" and not r["human_oversight"])
    eq("decides about people with no human oversight recorded", decides_no_review, ["SYS-04", "SYS-08", "SYS-14"])

    inc = [r for r in rows("incidents.csv") if r["unit"] in ("U1", "U2")]
    eq("incidents in the slice", len(inc), 8)
    eq("found by complaint", sum(r["found_by"] == "شكوى" for r in inc), 5)
    closed = [r for r in inc if r["status"] == "مغلق"]
    eq("closed without root cause", sorted(r["incident_id"] for r in closed if r["root_cause"] == "لا"), ["INC-01", "INC-02", "INC-08"])
    eq("severity 3 not reported to the committee", sorted(r["incident_id"] for r in inc if int(r["severity"]) >= 3 and r["reported_to_committee"] == "لا"), ["INC-02"])

    m = rows("committee_meetings.csv")
    items = sum(int(r["items"]) for r in m)
    eq("committee items in a year", items, 38)
    eq("approved", sum(int(r["approved"]) for r in m), 38)
    eq("with conditions", sum(int(r["of_which_with_conditions"]) for r in m), 3)
    eq("dissent recorded", sum(int(r["dissent_recorded"]) for r in m), 0)
    eq("meetings without quorum (fewer than 5 voting)", sorted(r["meeting"] for r in m if int(r["voting_present"]) < 5), ["M-02", "M-05", "M-08"])
    eq("meeting minutes per item", round(sum(int(r["meeting_minutes"]) for r in m) / items, 1), 6.3)

    # maturity levels by the course's model
    levels = {
        "D1": 2,  # P4 terms of reference exist; no charter; decisions not exercised (100% approval, quorum misses)
        "D2": 2 if any(months_since(p) > 0 for p in ("2025-03", "2026-01", "2025-09")) else 3,  # documents past review date
        "D3": 2 if round(100 * 21 / 60) < 80 else 3,  # roles partly named, owner training 35% (year_training.csv)
        "D4": 2 if (len(inv) / (len(inv) + len(unreg)) < 0.9 or no_owner or genai_hi) else 3,
        "D5": 2 if (sum(r["root_cause"] == "نعم" for r in closed) / len(closed) < 0.8) else 3,
        "D6": 1,  # no channel, no disclosure (I-02, I-05)
    }
    eq("maturity levels", levels, {"D1": 2, "D2": 2, "D3": 2, "D4": 2, "D5": 2, "D6": 1})
    eq("root cause rate of closed incidents %", round(100 * sum(r["root_cause"] == "نعم" for r in closed) / len(closed)), 57)

    by_id = {r["system_id"]: r for r in inv}
    tool_exp = {"T-01": 2, "T-02": 3, "T-03": 2}  # unassessed: T-02 suggests grades (affects people)

    def exp_of(ids):
        return max(exposure(by_id[i]) if i in by_id else tool_exp[i] for i in ids)

    gaps = {
        "A GenAI tools over Public data": (3, genai_hi + genai_hi_tools),
        "B Deciding or high systems without assessment or oversight": (2, ["SYS-02", "SYS-04", "SYS-08", "SYS-14"]),
        "C Register incomplete: unregistered tools, agents out of scope": (2, ["T-01", "T-02", "T-03", "SYS-04", "SYS-12", "SYS-21"]),
        "D Nominal committee oversight": (2, ["SYS-02", "SYS-08", "SYS-13"]),
        "E Incidents found by complaint, no root cause, not escalated": (2, ["SYS-04", "SYS-08", "SYS-13", "SYS-14", "T-01"]),
        "F Affected people and front line not heard": (2, ["SYS-08", "SYS-13", "SYS-14"]),
        "G Agents and pilots without an owner": (1, ["SYS-04", "SYS-14"]),
        "H Reviews overdue": (1, overdue),
        "I Policies out of date, owner approves own policy, no agent standard": (1, [r["system_id"] for r in inv]),
    }
    scored = sorted(((w * exp_of(ids), len(ids), k) for k, (w, ids) in gaps.items()), key=lambda t: (-t[0], -t[1]))
    eq("first four (score, systems, gap)", [(s, n, k[0]) for s, n, k in scored[:4]],
       [(9, 7, "A"), (6, 6, "C"), (6, 5, "E"), (6, 4, "B")])
    eq("fifth place is a tie: D and F, score 6 with 3 systems each",
       sorted((s, n, k[0]) for s, n, k in scored if k[0] in "DF"), [(6, 3, "D"), (6, 3, "F")])
    eq("below the cut (G, H, I)", sorted((k[0], s) for s, n, k in scored if k[0] in "GHI"), [("G", 3), ("H", 3), ("I", 3)])


# ------------------------------------------------------------------ lab 1.2
TIERS = {"T1": (24, 1, 2, 8, 3), "T2": (22, 1, 8, 6, 12), "T3": (14, 2, 24, 4, 40)}


def demand():
    existing = sum(n * per * h for n, per, h, _, _ in TIERS.values())
    new = sum(nn * hh for _, _, _, nn, hh in TIERS.values())
    return existing, new, existing + new + 40


@lab("1.2")
def lab_1_2():
    existing, new, total = demand()
    eq("existing reviews, hours", existing, 896)
    eq("new intake, hours", new, 256)
    eq("total demand with staff tools, hours", total, 1192)
    models = {"مركزي": (2 * 1400 * 0.7, 1.25), "اتحادي": (6 * 0.25 * 1400 * 1.0, 1.00), "المحور والأطراف": (1.5 * 1400 * 0.7 + 6 * 0.1 * 1400, 1.10)}
    out = {k: (round(cap), round(total * f), round(100 * total * f / cap)) for k, (cap, f) in models.items()}
    eq("capacity, adjusted demand, utilisation %", out, {"مركزي": (1960, 1490, 76), "اتحادي": (2100, 1192, 57), "المحور والأطراف": (2310, 1311, 57)})
    weights = [25, 20, 20, 20, 15]
    ref = {"مركزي": [5, 3, 2, 4, 3], "اتحادي": [2, 4, 5, 2, 4], "المحور والأطراف": [4, 4, 4, 4, 3]}
    eq("reference weighted scores (of 500)", {k: sum(a * b for a, b in zip(weights, v)) for k, v in ref.items()},
       {"مركزي": 350, "اتحادي": 330, "المحور والأطراف": 385})
    eq("FTE per model", {k: v for k, v in {"مركزي": 2.0, "اتحادي": 6 * 0.25, "المحور والأطراف": 1.5 + 6 * 0.1}.items()},
       {"مركزي": 2.0, "اتحادي": 1.5, "المحور والأطراف": 2.1})
    # decision rights reference: (drafts or proposes, approves, assures); no decision has one role in two columns
    rights = {
        1: ("مالك النظام", "قائد مكتب الحوكمة", "التدقيق الداخلي"),
        2: ("مالك النظام", "قائد مكتب الحوكمة", "اللجنة"),
        3: ("مالك النظام", "اللجنة", "التدقيق الداخلي"),
        4: ("مالك النظام", "قائد مكتب الحوكمة أو رئيس اللجنة", "اللجنة"),
        5: ("مالك النظام", "اللجنة؛ والمستوى 16 اللجنة التنفيذية", "التدقيق الداخلي"),
        6: ("مالك النظام يوقف فورًا", "قائد مكتب الحوكمة يأمر عند الحاجة", "اللجنة"),
        7: ("قائد مكتب الحوكمة", "الوزير بتوصية اللجنة", "التدقيق الداخلي"),
        8: ("التدقيق الداخلي", "الوزير", "مراجع خارجي"),
    }
    eq("decision rights with three distinct roles", all(len(set(v)) == 3 for v in rights.values()), True)


# ------------------------------------------------------------------ lab 2.1
@lab("2.1")
def lab_2_1():
    req = {  # likelihood, impact, agent acting on cases, decides without review, GenAI on data above Public
        "A": (2, 2, False, False, True),
        "B": (1, 2, False, False, False),
        "C": (2, 3, True, False, False),
        "D": (2, 3, False, False, False),
        "E": (3, 4, False, True, False),
    }
    tiers, stop = {}, []
    for k, (l, i, agent, auto, genai_hi) in req.items():
        lvl = l * i
        t = "T1" if lvl <= 2 else "T2" if lvl <= 6 else "T3" if lvl <= 12 else "STOP"
        if agent or auto:
            t = "T3"
        tiers[k] = (lvl, t)
        if genai_hi:
            stop.append(k)
    eq("level and tier", tiers, {"A": (4, "T2"), "B": (2, "T1"), "C": (6, "T3"), "D": (6, "T2"), "E": (12, "T3")})
    eq("stopped at G0 for data", stop, ["A"])
    log = rows("gate_log.csv")
    first = {}
    last = {}
    for r in log:
        first.setdefault(r["request"], iso(r["submitted"]))
        last[r["request"]] = iso(r["decided"])
    elapsed = {k: workdays(first[k], last[k]) for k in sorted(first)}
    eq("working days from complete request to last decision", elapsed, {"A": 2, "B": 21, "C": 19, "D": 16, "E": 15})
    sla = {"T1": 3, "T2": 10, "T3": 20}
    recorded = {r["request"]: r["tier_recorded"] for r in log}
    eq("tier recorded by the office", recorded, {"A": "T1", "B": "T1", "C": "T2", "D": "T2", "E": "T3"})
    eq("breaches against the correct tier", sorted(k for k in elapsed if elapsed[k] > sla[tiers[k][1]]), ["B", "D"])
    eq("waited for the monthly committee (decided 2026-10-05) though not T3",
       sorted({r["request"] for r in log if r["decided"] == "2026-10-05" and tiers[r["request"]][1] != "T3"}), ["B", "D"])


# ------------------------------------------------------------------ lab 3.1
@lab("3.1")
def lab_3_1():
    voting = 7
    cases = {"1": (1, 0), "2": (1, 2), "3": (1, 0)}  # absent, recused
    quorum = {k: voting - a - r for k, (a, r) in cases.items()}
    eq("voting members counting for quorum", quorum, {"1": 6, "2": 4, "3": 6})
    eq("quorum met (5 needed)", {k: v >= 5 for k, v in quorum.items()}, {"1": True, "2": False, "3": True})
    eq("non-conflicted voting members for circulation in dossier 2", voting - 2, 5)
    eq("dossier 3 residual level", 4 * 4, 16)
    eq("dossier 1 error rate after the fix, per 1,000 messages", round(1000 * 6 / 2400, 1), 2.5)


# ------------------------------------------------------------------ lab 3.2
def quarter(d: str) -> str:
    y, m = map(int, d[:7].split("-"))
    q = {11: "Q1", 12: "Q1", 1: "Q1", 2: "Q2", 3: "Q2", 4: "Q2", 5: "Q3", 6: "Q3", 7: "Q3", 8: "Q4", 9: "Q4", 10: "Q4"}[m]
    return q


@lab("3.2")
def lab_3_2():
    req = rows("year_requests.csv")
    eq("requests in the year", len(req), 141)
    by_q = {}
    for r in req:
        by_q.setdefault(quarter(r["submitted"]), []).append(r)
    eq("requests per quarter (activity)", {q: len(v) for q, v in sorted(by_q.items())}, {"Q1": 25, "Q2": 31, "Q3": 39, "Q4": 46})
    eq("% within SLA per quarter", {q: round(100 * sum(r["within_sla"] == "نعم" for r in v) / len(v)) for q, v in sorted(by_q.items())},
       {"Q1": 60, "Q2": 61, "Q3": 38, "Q4": 17})
    tiers = {}
    for r in req:
        tiers.setdefault(r["tier"], []).append(r)
    eq("% within SLA per tier", {t: round(100 * sum(r["within_sla"] == "نعم" for r in v) / len(v)) for t, v in sorted(tiers.items())},
       {"T1": 22, "T2": 48, "T3": 63})
    eq("median working days per tier", {t: st.median(int(r["working_days"]) for r in v) for t, v in sorted(tiers.items())},
       {"T1": 5, "T2": 11, "T3": 19.5})
    t3h2 = [r for r in tiers["T3"] if r["submitted"] >= "2026-05"]
    eq("T3 requests from May 2026, approved without any condition", (sum(r["decision"] == "موافقة" and r["conditions"] == "0" for r in t3h2), len(t3h2)), (19, 19))
    t3h1 = [r for r in tiers["T3"] if r["submitted"] < "2026-05"]
    eq("T3 requests before May 2026: with conditions, returned or refused", sum(r["decision"] != "موافقة" for r in t3h1), 8)

    inc = rows("year_incidents.csv")
    eq("incidents and share found by monitoring %", (len(inc), round(100 * sum(r["found_by"] == "مراقبة" for r in inc) / len(inc))), (20, 20))
    eq("median days to contain: monitoring vs others",
       (st.median(int(r["days_to_contain"]) for r in inc if r["found_by"] == "مراقبة"),
        st.median(int(r["days_to_contain"]) for r in inc if r["found_by"] != "مراقبة")), (2, 17))
    exc = rows("year_exceptions.csv")
    eq("open exceptions with no expiry", sorted(r["exception_id"] for r in exc if r["status"] == "مفتوح" and not r["expires"]), ["X-02", "X-04", "X-07", "X-10", "X-12"])
    eq("open exceptions past expiry at the end of October 2026", sorted(r["exception_id"] for r in exc if r["status"] == "مفتوح" and r["expires"] and r["expires"] < "2026-10"), ["X-06", "X-08"])
    tr = rows("year_training.csv")
    eq("training % against target", {r["role"]: (round(100 * int(r["completed"]) / int(r["headcount"])), int(r["target_percent"])) for r in tr},
       {"مالكو الأنظمة": (35, 90), "أعضاء لجنة الحوكمة": (100, 100), "المطورون وفرق البيانات": (78, 90),
        "مشرفو الخط الأمامي": (33, 80), "كل الموظفين: أساسيات الاستخدام المسؤول": (85, 80)})
    hours = rows("year_office_hours.csv")
    used = sum(int(r["review_hours"]) for r in hours)
    eq("office review hours in the year, and utilisation of 3 FTE x 1,400 %", (used, round(100 * used / (3 * 1400))), (3133, 75))
    last_q = by_q["Q4"]
    per_month = len(last_q) / 3
    share = {t: len(v) / len(req) for t, v in tiers.items()}
    forecast = {t: round(per_month * 12 * share[t]) for t in sorted(share)}
    eq("next-year requests by tier at the last quarter's pace", forecast, {"T1": 77, "T2": 68, "T3": 39})
    hrs = forecast["T1"] * 3 + forecast["T2"] * 12 + forecast["T3"] * 40 + 896 + 40
    eq("next-year demand, hours", hrs, 3543)
    eq("FTE needed at 1,400 h and 75%", round(hrs / (1400 * 0.75), 1), 3.4)
    eq("last quarter pace: requests per month, per year", (round(per_month, 1), round(per_month * 12)), (15.3, 184))
    eq("sensitivity: T3 intake 30 h instead of 40, hours saved and FTE", (forecast["T3"] * 10, round(forecast["T3"] * 10 / 1050, 1)), (390, 0.4))
    eq("incidents found by monitoring, count", sum(r["found_by"] == "مراقبة" for r in inc), 4)
    eq("exceptions open with no expiry or past expiry", 5 + 2, 7)


# ------------------------------------------------------------------ slide examples (parallel, unit U4)
@lab("ex")
def examples():
    u4 = [r for r in rows("inventory.csv") if r["unit"] == "U4"]
    eq("U4 systems on the slides", len(u4), 11)
    s33 = next(r for r in u4 if r["system_id"] == "SYS-33")
    eq("SYS-33 (tiers slide): likelihood, impact, level, decision role",
       (s33["likelihood"], s33["impact"], s33["risk_level"], s33["decision_role"]), ("3", "2", "6", "يقرر"))
    eq("parallel utilisation example: 900 h on 1 FTE at 70%", round(100 * 900 / (1400 * 0.7)), 92)
    eq("parallel quorum example: 9 voting, 2 absent, 3 recused, quorum 6", 9 - 2 - 3 >= 6, False)
    eq("parallel FTE example: 2,100 h at 1,400 h and 75%", round(2100 / (1400 * 0.75), 1), 2.0)
    eq("parallel SLA example: submitted Sunday 2026-03-01, decided Thursday 2026-03-12", workdays(date(2026, 3, 1), date(2026, 3, 12)), 9)


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    pick = argv or list(LABS)
    for k in pick:
        print(f"lab {k}")
        LABS[k]()
        print("  PASS")
    print("all PASS")


if __name__ == "__main__":
    main(sys.argv[1:])
