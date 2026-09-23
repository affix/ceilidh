from ceilidh import library

SM = ("#TITLE:{title};\n#ARTIST:A;\n#BPMS:0=120;\n#OFFSET:0;\n"
      "#NOTES:\n dance-single:\n :\n Easy:\n 3:\n 0,0,0,0,0:\n1000\n0000\n0000\n0000\n;\n")


def song_folder(parent, name, audio=True):
    folder = parent / name
    folder.mkdir(parents=True)
    (folder / "song.sm").write_text(SM.format(title=name))
    if audio:
        (folder / "song.ogg").write_bytes(b"OggS")
    return folder


def test_a_folder_holding_a_simfile_is_a_song(tmp_path):
    song_folder(tmp_path, "Solo Song")
    songs, errors = library.scan([tmp_path])
    assert [s.title for s in songs] == ["Solo Song"]
    assert errors == []


def test_the_folder_above_a_song_names_its_pack(tmp_path):
    song_folder(tmp_path / "Great Pack", "Song One")
    song_folder(tmp_path / "Great Pack", "Song Two")
    songs, _ = library.scan([tmp_path])
    assert {s.pack for s in songs} == {"Great Pack"}
    assert len(songs) == 2


def test_a_song_sitting_directly_in_a_root_has_no_pack(tmp_path):
    song_folder(tmp_path, "Loose")
    songs, _ = library.scan([tmp_path])
    assert songs[0].pack == ""


def test_a_song_with_no_audio_is_reported_not_returned(tmp_path):
    song_folder(tmp_path, "Silent", audio=False)
    songs, errors = library.scan([tmp_path])
    assert songs == []
    assert len(errors) == 1 and "no audio" in errors[0]


def test_a_broken_simfile_does_not_take_the_library_down(tmp_path):
    song_folder(tmp_path / "Pack", "Good")
    broken = tmp_path / "Pack" / "Broken"
    broken.mkdir()
    (broken / "bad.sm").write_text("#TITLE:Nope;")
    (broken / "bad.ogg").write_bytes(b"OggS")
    songs, errors = library.scan([tmp_path])
    assert [s.title for s in songs] == ["Good"]
    assert len(errors) == 1


def test_songs_come_back_sorted_by_pack_then_title(tmp_path):
    song_folder(tmp_path / "Beta", "Zulu")
    song_folder(tmp_path / "Alpha", "Yankee")
    song_folder(tmp_path / "Alpha", "Xray")
    songs, _ = library.scan([tmp_path])
    assert [(s.pack, s.title) for s in songs] == [
        ("Alpha", "Xray"), ("Alpha", "Yankee"), ("Beta", "Zulu")]


def test_hidden_folders_are_left_alone(tmp_path):
    song_folder(tmp_path / ".hidden", "Secret")
    songs, _ = library.scan([tmp_path])
    assert songs == []


def test_missing_roots_are_simply_skipped(tmp_path):
    song_folder(tmp_path, "Real")
    songs, errors = library.scan([tmp_path / "nowhere", tmp_path])
    assert len(songs) == 1 and errors == []


def test_the_same_root_twice_does_not_duplicate_songs(tmp_path):
    song_folder(tmp_path, "Once")
    songs, _ = library.scan([tmp_path, tmp_path])
    assert len(songs) == 1


def test_songs_buried_too_deep_are_not_found(tmp_path):
    song_folder(tmp_path / "a" / "b" / "c" / "d" / "e", "Deep")
    songs, _ = library.scan([tmp_path], max_depth=3)
    assert songs == []
