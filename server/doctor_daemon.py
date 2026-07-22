"""Doctor Daemon — the AUTOMATIC half of the self-learning agent.

plan_doctor.py grades every single parse live. THIS script is the slower
brain that runs on a schedule (Windows Task Scheduler -> run_doctor_daily.bat,
e.g. every night at 02:00): it re-reads the whole learning log, finds trends
a single parse can't show, and writes a short human report.

What it does each run (all in plain language, no ML required):
 1. Reads docs/LEARNINGS.md (every parse the Plan Doctor ever graded).
 2. Aggregates: parses & grade mix in the last 24h vs all-time, the most
    common failure tags, and the worst recent plans.
 3. Writes docs/DOCTOR-DAILY.md — the founder's morning read.
 4. Optional: with LLM_DOCTOR=1 + ANTHROPIC_API_KEY it asks a small Claude
    model for a 3-sentence trend summary + one improvement suggestion,
    appended to the report (never replaces the numbers).

Run manually any time:  python doctor_daemon.py
Exit code is always 0 unless the log is unreadable — safe for schedulers.
"""
import json
import os
import re
import sys
import time
from collections import Counter

LINE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) \| (.*?) \| grade ([A-F]) "
    r"\((\d+)/100\) \| tags: (.*?) \| (.*)$")


def _paths():
    here = os.path.dirname(os.path.abspath(__file__))
    docs = os.path.join(here, "..", "docs")
    src = os.getenv("LEARNINGS_FILE") or os.path.join(docs, "LEARNINGS.md")
    out = os.getenv("DOCTOR_DAILY_FILE") or os.path.join(docs, "DOCTOR-DAILY.md")
    return src, out


def parse_log(text):
    """LEARNINGS.md text -> list of entry dicts (bad lines are skipped)."""
    entries = []
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        date, hhmm, fname, grade, score, tags, headline = m.groups()
        entries.append({
            "date": date, "time": hhmm, "file": fname.strip(),
            "grade": grade, "score": int(score),
            "tags": [] if tags.strip() == "clean"
                    else [t.strip() for t in tags.split(",") if t.strip()],
            "headline": headline.strip(),
        })
    return entries


def summarize(entries, today):
    """Entries -> digest dict. `today` = 'YYYY-MM-DD' (injected, testable)."""
    recent = [e for e in entries if e["date"] == today]
    grades_all = Counter(e["grade"] for e in entries)
    grades_today = Counter(e["grade"] for e in recent)
    tags = Counter(t for e in entries for t in e["tags"])
    tags_today = Counter(t for e in recent for t in e["tags"])
    worst = sorted(recent or entries, key=lambda e: e["score"])[:5]
    avg = lambda xs: round(sum(x["score"] for x in xs) / len(xs), 1) if xs else None
    return {
        "total": len(entries), "today": len(recent),
        "avg_score_all": avg(entries), "avg_score_today": avg(recent),
        "grades_all": dict(grades_all), "grades_today": dict(grades_today),
        "top_tags_all": tags.most_common(6),
        "top_tags_today": tags_today.most_common(6),
        "worst": worst,
    }


# what each failure tag means for a founder + what fixes it (layman glossary)
TAG_HELP = {
    "no_rooms": "walls don't close into rooms -> carpet/efficiency unavailable"
                " (worst offender; parser wall-repair work fixes this)",
    "no_rooms_fallback": "rooms missing but carpet estimated from wall interior",
    "efficiency_zero": "efficiency shown as 'needs review' (carpet unknown)",
    "scale_assumed": "no dimension text -> sizes based on an assumed width",
    "scale_column_guess": "scale guessed from 12-inch columns (verify a room)",
    "no_doors": "no door symbols found -> sealed rooms in 3D",
    "no_windows": "no window tags found on the sheet",
    "rooms_unlabeled": "room names are pictures, not text (OCR/tesseract helps)",
    "tiny_rooms": "shafts/pockets counted as rooms (count inflated)",
    "door_width_odd": "door sizes implausible -> scale suspicion",
    "envelope_implausible": "building size outside 12-400 ft -> scale failed",
    "ml_reader": "read by the AI photo path (approximate walls)",
}


def render(digest, today):
    g = lambda d: ", ".join(f"{k}:{v}" for k, v in sorted(d.items())) or "none"
    lines = [
        "# Doctor Daily — automatic health report",
        f"_Written by doctor_daemon.py on {today}. Numbers come from every "
        "parse the Plan Doctor graded (docs/LEARNINGS.md)._",
        "",
        f"**Today:** {digest['today']} parse(s), average score "
        f"{digest['avg_score_today'] if digest['avg_score_today'] is not None else '—'}"
        f"/100, grades: {g(digest['grades_today'])}",
        f"**All-time:** {digest['total']} parse(s), average score "
        f"{digest['avg_score_all'] if digest['avg_score_all'] is not None else '—'}"
        f"/100, grades: {g(digest['grades_all'])}",
        "",
        "## What is failing most (all-time)",
        "",
    ]
    if digest["top_tags_all"]:
        for tag, n in digest["top_tags_all"]:
            lines.append(f"- **{tag}** x{n} — {TAG_HELP.get(tag, 'see plan_doctor.py')}")
    else:
        lines.append("- Nothing yet — every graded parse was clean.")
    lines += ["", "## Worst recent parses (fix-first list)", ""]
    for e in digest["worst"]:
        lines.append(f"- {e['file']} — grade {e['grade']} ({e['score']}/100): "
                     f"{e['headline'][:140]}")
    if not digest["worst"]:
        lines.append("- None.")
    lines += ["", "_Improvement rule: the top tag above is the single highest-"
              "value parser fix. Hand this file to Claude and say 'fix the top"
              " tag' — that is the self-learning loop._", ""]
    return "\n".join(lines)


def llm_trend_note(digest):
    """Optional 3-sentence LLM read of the trends (same gates as plan_doctor)."""
    try:
        import plan_doctor
        if not plan_doctor.llm_enabled():
            return None
        import httpx
        prompt = ("You are the QA analyst for a floor-plan-to-3D product. In "
                  "3 plain-English sentences for a non-technical founder: "
                  "summarize the health trend and suggest ONE next fix. Data: "
                  + json.dumps({k: digest[k] for k in
                                ("today", "total", "avg_score_today",
                                 "avg_score_all", "top_tags_all")})[:1500])
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01"},
            json={"model": os.getenv("LLM_DOCTOR_MODEL", "claude-haiku-4-5"),
                  "max_tokens": 250,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=20.0)
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    except Exception:
        return None


def main():
    src, out = _paths()
    if not os.path.exists(src):
        print("no learning log yet — nothing to report")
        return 0
    with open(src, encoding="utf-8") as f:
        entries = parse_log(f.read())
    today = time.strftime("%Y-%m-%d")
    digest = summarize(entries, today)
    report = render(digest, today)
    note = llm_trend_note(digest)
    if note:
        report += f"\n## LLM trend note\n\n{note.strip()[:800]}\n"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"doctor daily written: {out} ({digest['total']} parses, "
          f"{digest['today']} today)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
