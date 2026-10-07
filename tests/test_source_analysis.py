import json

from yt_kotoba.context import normalize_comments
from yt_kotoba.repair import find_loop_spans, is_loop_text
from yt_kotoba.source_pack import build_source_pack_manifest
from yt_kotoba.visual import count_changes, frame_diffs


def seg(offset_s, text, dur_s=5):
    return {"text": text, "offset": offset_s * 1000, "duration": dur_s * 1000}


def test_loop_text_detects_short_phrase_repeats():
    assert is_loop_text("既に、" * 30)
    assert is_loop_text("thank you " * 20)
    assert not is_loop_text("今日は定年後の過ごし方について、7つの習慣を紹介します。")
    assert not is_loop_text("短い")


def test_find_loop_spans_merges_and_pads():
    segments = [
        seg(0, "最初の話です。ここは普通に聞き取れています。"),
        seg(60, "既に、" * 20),
        seg(65, "既に、" * 20),
        seg(120, "ここからまた普通の話に戻ります。"),
    ]
    spans = find_loop_spans(segments, pad_ms=10_000)
    assert spans == [(50_000, 80_000)]


def test_find_loop_spans_catches_identical_segment_runs():
    same = "ご視聴ありがとうございました"
    segments = [seg(i * 5, same) for i in range(5)]
    assert find_loop_spans(segments, pad_ms=0)


def test_find_loop_spans_none_for_clean_transcript():
    segments = [seg(i * 5, f"これは{i}番目の普通の文です。") for i in range(10)]
    assert find_loop_spans(segments) == []


def test_normalize_comments_splits_roles():
    raw = [
        {"id": "a", "parent": "root", "author": "@viewer1", "text": "参考になりました", "like_count": 3},
        {"id": "b", "parent": "root", "author": "@channel", "author_is_uploader": True,
         "is_pinned": True, "text": "何位が好き？", "like_count": 6},
        {"id": "c", "parent": "a", "author": "@channel", "author_is_uploader": True, "text": "ありがとう"},
        {"id": "d", "parent": "a", "author": "@viewer2", "text": "同じく", "extra": "dropped"},
    ]
    out = normalize_comments(raw, "ok")
    assert out["counts"] == {"total": 4, "root": 2, "replies": 2, "uploader_posts": 2, "viewer_root": 1}
    assert "extra" not in out["comments"][3]


def test_normalize_comments_records_status_without_data():
    out = normalize_comments(None, "disabled_or_unavailable")
    assert out["status"] == "disabled_or_unavailable"
    assert out["counts"]["total"] == 0


def test_count_changes_merges_consecutive_frames():
    diffs = [0, 30, 30, 0, 0, 30, 0, 10, 0]
    assert count_changes(diffs, 25) == 2
    assert count_changes(diffs, 8) == 3


def test_frame_diffs_on_synthetic_frames():
    size = 4
    raw = bytes([0] * size + [0] * size + [100] * size)
    assert frame_diffs(raw, frame_size=size) == [0.0, 100.0]


def test_manifest_lists_analysis_files(tmp_path):
    (tmp_path / "metadata.json").write_text(json.dumps({"id": "abcdefghijk", "title": "t"}))
    (tmp_path / "comments.json").write_text(json.dumps(normalize_comments([], "ok")))
    (tmp_path / "visual_rhythm.json").write_text("{}")
    (tmp_path / "frames" / "every_10s").mkdir(parents=True)
    m = build_source_pack_manifest(tmp_path)
    assert m["files"]["internal_analysis"]["visual_rhythm"]["exists"]
    assert m["files"]["visual_samples"]["frames_every_10s"]["exists"]
    assert m["comments"]["counts"]["total"] == 0
    assert m["files"]["source"]["transcript_repair"]["exists"] is False
