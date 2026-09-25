
from epilepticcli.config import Config
from epilepticcli.core.agents import load_agent
from epilepticcli.core.prompts import compose_system_prompt


def make_cfg(builtin=True):
    return Config(raw={}, builtin_system_prompt=builtin)


def test_builtin_prompt_included(tmp_path):
    p = compose_system_prompt(make_cfg(), tmp_path)
    assert "EpilepticCLI" in p


def test_raw_mode_drops_builtin(tmp_path):
    (tmp_path / "EPIC.md").write_text("mem")
    p = compose_system_prompt(make_cfg(), tmp_path, raw_mode=True)
    assert "You are EpilepticCLI" not in p
    assert "mem" in p


def test_memory_files_merged(tmp_path):
    (tmp_path / "AGENTS.md").write_text("rules")
    p = compose_system_prompt(make_cfg(), tmp_path)
    assert "rules" in p


def test_agent_frontmatter(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("---\nname: x\ndescription: d\ntools: [grep]\nmodel: m\n---\n\nbody prompt\n")
    a = load_agent(f)
    assert a.name == "x"
    assert a.tools == ["grep"]
    assert a.model == "m"
    assert a.prompt.strip() == "body prompt"
