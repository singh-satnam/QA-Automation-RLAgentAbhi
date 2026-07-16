import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import test_data_io as tdio


# ---- flatten / parse -------------------------------------------------------
def test_flatten_scalars():
    out = tdio.flatten_json_to_dotenv(
        {"URL": "https://app", "user name": "qa", "n": 3, "ok": True, "x": None}
    )
    lines = out.strip().splitlines()
    assert "URL=https://app" in lines
    assert "USER_NAME=qa" in lines          # key upper-cased, space -> _
    assert "N=3" in lines
    assert "OK=true" in lines               # bool lower-cased
    assert "X=" in lines                    # None -> empty
    assert out.endswith("\n")


def test_flatten_nested_is_json_encoded():
    out = tdio.flatten_json_to_dotenv({"CFG": {"a": 1}, "LIST": [1, 2]})
    # A dict value contains '"', so it is dotenv-quoted+escaped; a plain list is not.
    assert "LIST=[1,2]" in out
    # Round-trip: parsing the .env recovers the compact JSON string intact.
    parsed = tdio.parse_dotenv(out)
    assert parsed["CFG"] == '{"a":1}'
    assert parsed["LIST"] == "[1,2]"


def test_flatten_quotes_values_with_specials():
    out = tdio.flatten_json_to_dotenv({"NOTE": "a # b", "MULTI": "l1\nl2"})
    assert 'NOTE="a # b"' in out
    assert 'MULTI="l1\\nl2"' in out


def test_flatten_rejects_non_dict():
    with pytest.raises(ValueError):
        tdio.flatten_json_to_dotenv([1, 2, 3])


def test_parse_dotenv_roundtrip_and_comments():
    text = "# comment\n\nURL=https://app\nNOTE=\"a # b\"\nBLANKVAL=\n"
    d = tdio.parse_dotenv(text)
    assert d == {"URL": "https://app", "NOTE": "a # b", "BLANKVAL": ""}


def test_parse_dotenv_first_equals_wins():
    d = tdio.parse_dotenv("TOKEN=ab=cd\n")
    assert d["TOKEN"] == "ab=cd"


# ---- writers / resolver ----------------------------------------------------
def test_write_global_env(tmp_path):
    ok, msg = tdio.write_global_env(tmp_path, '{"URL":"https://app","PASSWORD":"p@ss"}')
    assert ok, msg
    env = (tmp_path / "test_data" / ".env").read_text(encoding="utf-8")
    assert "URL=https://app" in env
    assert "PASSWORD=p@ss" in env
    raw = json.loads((tmp_path / "test_data" / "global_project_data.json").read_text(encoding="utf-8"))
    assert raw["URL"] == "https://app"


def test_write_global_env_rejects_array(tmp_path):
    ok, msg = tdio.write_global_env(tmp_path, "[1,2,3]")
    assert not ok
    assert not (tmp_path / "test_data" / ".env").exists()


def test_write_story_data_json(tmp_path):
    ok, msg = tdio.write_story_data(tmp_path, "RLRG_login", "RLRG_login.json", b'{"productid":"123"}')
    assert ok, msg
    saved = json.loads((tmp_path / "test_data" / "RLRG_login.json").read_text(encoding="utf-8"))
    assert saved["productid"] == "123"


def test_write_story_data_csv_preserves_original(tmp_path):
    ok, msg = tdio.write_story_data(tmp_path, "RLRG_login", "data.csv", b"a,b\n1,2\n")
    assert ok, msg
    assert (tmp_path / "test_data" / "RLRG_login.json").exists()
    assert (tmp_path / "test_data" / "RLRG_login.csv").read_bytes() == b"a,b\n1,2\n"


def test_resolve_story_data_file(tmp_path):
    td = tmp_path / "test_data"
    td.mkdir()
    (td / "global_project_data.json").write_text("{}", encoding="utf-8")
    (td / "RLRG_login.json").write_text("{}", encoding="utf-8")
    assert tdio.resolve_story_data_file(td, "RLRG_login").name == "RLRG_login.json"
    assert tdio.resolve_story_data_file(td, "login").name == "RLRG_login.json"  # substring
    assert tdio.resolve_story_data_file(td, "nope") is None
    assert tdio.resolve_story_data_file(td, "global_project_data") is None      # excluded
