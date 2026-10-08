from yt_kotoba.diarize import UNKNOWN_SPEAKER, assign_speakers


def test_assign_speakers_uses_largest_overlap_without_mutating_input():
    transcript = {
        "segments": [
            {"text": "hello", "offset": 0, "duration": 1500},
            {"text": "there", "offset": 1500, "duration": 1500},
        ],
        "fullText": "hello there",
        "lang": "en",
    }
    turns = [
        {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 3.0, "speaker": "SPEAKER_01"},
    ]

    result = assign_speakers(transcript, turns)

    assert [segment["speaker"] for segment in result["segments"]] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]
    assert "speaker" not in transcript["segments"][0]


def test_assign_speakers_marks_segments_without_overlap_as_unknown():
    transcript = {
        "segments": [{"text": "silence hallucination", "offset": 5000, "duration": 500}],
        "fullText": "silence hallucination",
        "lang": "en",
    }

    result = assign_speakers(
        transcript,
        [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}],
    )

    assert result["segments"][0]["speaker"] == UNKNOWN_SPEAKER
