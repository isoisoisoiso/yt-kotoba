from yt_kotoba.pack_transcript import pack_transcript


def test_pack_transcript_keeps_speaker_changes_in_separate_blocks():
    transcript = {
        "segments": [
            {
                "text": "first",
                "offset": 0,
                "duration": 1000,
                "speaker": "SPEAKER_00",
            },
            {
                "text": "second",
                "offset": 1000,
                "duration": 1000,
                "speaker": "SPEAKER_01",
            },
        ],
        "lang": "en",
    }

    packed = pack_transcript(transcript)

    assert "- Speakers: SPEAKER_00, SPEAKER_01" in packed
    assert "## [00:00] SPEAKER_00" in packed
    assert "## [00:01] SPEAKER_01" in packed
