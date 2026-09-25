import json

from epilepticcli.tools.registry import build_tools, run_tool


def call(tools, name, **args):
    return run_tool(tools, name, json.dumps(args))


def test_file_roundtrip(tmp_path):
    tools = build_tools(tmp_path)
    r = call(tools, "write_file", path="a.txt", content="hello\nworld\n")
    assert not r.is_error
    r = call(tools, "read_file", path="a.txt")
    assert "hello" in r.content
    r = call(tools, "edit_file", path="a.txt", old_string="world", new_string="epi")
    assert not r.is_error
    assert (tmp_path / "a.txt").read_text() == "hello\nepi\n"


def test_edit_requires_unique(tmp_path):
    (tmp_path / "b.txt").write_text("x x x")
    tools = build_tools(tmp_path)
    r = call(tools, "edit_file", path="b.txt", old_string="x", new_string="y")
    assert r.is_error
    r = call(tools, "edit_file", path="b.txt", old_string="x", new_string="y", replace_all=True)
    assert not r.is_error


def test_grep_and_glob(tmp_path):
    (tmp_path / "c.py").write_text("def foo():\n    return 1\n")
    tools = build_tools(tmp_path)
    assert "foo" in call(tools, "grep", pattern="foo").content
    assert "c.py" in call(tools, "glob", pattern="*.py").content


def test_shell(tmp_path):
    tools = build_tools(tmp_path)
    r = call(tools, "run_shell", command="echo hi")
    assert "hi" in r.content


def test_unknown_tool(tmp_path):
    tools = build_tools(tmp_path)
    r = run_tool(tools, "nope", "{}")
    assert r.is_error
