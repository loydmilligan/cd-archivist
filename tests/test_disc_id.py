from pathlib import Path

from cd_archivist.disc_id import next_disc_id


def test_next_disc_id_starts_at_one(tmp_path: Path) -> None:
    assert next_disc_id(tmp_path) == "CD_0001"


def test_next_disc_id_increments(tmp_path: Path) -> None:
    (tmp_path / "CD_0001").mkdir()
    (tmp_path / "CD_0002").mkdir()
    assert next_disc_id(tmp_path) == "CD_0003"


def test_next_disc_id_ignores_other_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello")
    (tmp_path / "CD_ABCD").mkdir()
    assert next_disc_id(tmp_path) == "CD_0001"
