"""Doctor Daemon — nightly digest over the learning log (pure parts)."""
import doctor_daemon as DD

LOG = """# Drishti learning log (written by Plan Doctor)

- 2026-07-22 14:56 | brickwork.pdf | grade F (0/100) | tags: no_rooms, efficiency_zero | No rooms were detected.
- 2026-07-22 15:10 | 342.pdf | grade A (100/100) | tags: clean | All checks passed.
- 2026-07-21 09:00 | old.pdf | grade C (64/100) | tags: scale_assumed, no_windows | No dimension text was found.
garbage line that must be skipped
"""


def test_parse_log_reads_entries_and_skips_garbage():
    es = DD.parse_log(LOG)
    assert len(es) == 3
    assert es[0]["grade"] == "F" and es[0]["score"] == 0
    assert es[1]["tags"] == []                    # 'clean' -> no tags
    assert es[2]["tags"] == ["scale_assumed", "no_windows"]


def test_summarize_splits_today_vs_alltime():
    d = DD.summarize(DD.parse_log(LOG), today="2026-07-22")
    assert d["total"] == 3 and d["today"] == 2
    assert d["grades_today"] == {"F": 1, "A": 1}
    assert d["avg_score_today"] == 50.0
    assert d["top_tags_all"][0][0] in ("no_rooms", "efficiency_zero",
                                       "scale_assumed", "no_windows")


def test_render_is_layman_readable():
    d = DD.summarize(DD.parse_log(LOG), today="2026-07-22")
    md = DD.render(d, "2026-07-22")
    assert "Doctor Daily" in md
    assert "walls don't close" in md              # tag glossary in plain words
    assert "brickwork.pdf" in md                  # worst list names the file


def test_main_end_to_end(tmp_path, monkeypatch):
    src = tmp_path / "LEARNINGS.md"; src.write_text(LOG, encoding="utf-8")
    out = tmp_path / "DOCTOR-DAILY.md"
    monkeypatch.setenv("LEARNINGS_FILE", str(src))
    monkeypatch.setenv("DOCTOR_DAILY_FILE", str(out))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert DD.main() == 0
    assert "Doctor Daily" in out.read_text(encoding="utf-8")


def test_main_without_log_is_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGS_FILE", str(tmp_path / "missing.md"))
    monkeypatch.setenv("DOCTOR_DAILY_FILE", str(tmp_path / "out.md"))
    assert DD.main() == 0
