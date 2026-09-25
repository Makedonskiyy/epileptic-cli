from epilepticcli.core.session import Session


def test_session_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr("epilepticcli.core.session.SESSIONS_DIR", tmp_path)
    s = Session.new("demo", "demo")
    s.messages = [{"role": "user", "content": "hi"}]
    s.input_tokens = 3
    s.save()
    loaded = Session.load(s.id)
    assert loaded.messages[0]["content"] == "hi"
    assert loaded.input_tokens == 3


def test_export(tmp_path, monkeypatch):
    monkeypatch.setattr("epilepticcli.core.session.SESSIONS_DIR", tmp_path)
    s = Session.new("demo", "demo")
    s.messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]
    out = s.export_markdown()
    text = out.read_text()
    assert "hi" in text and "yo" in text
