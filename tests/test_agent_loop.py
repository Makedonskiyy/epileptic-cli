import json

from epilepticcli.core.agent import run_agent_turn
from epilepticcli.providers.base import AssistantMessage, Provider, ToolCall
from epilepticcli.tools.registry import build_tools


class ScriptedProvider(Provider):
    """Returns scripted responses in sequence."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def stream_chat(self, messages, model, tools=None, temperature=None,
                    max_tokens=None, on_delta=None):
        self.calls += 1
        resp = self.responses.pop(0)
        if on_delta and resp.content:
            on_delta(resp.content)
        return resp


def test_tool_call_loop(tmp_path):
    provider = ScriptedProvider(
        [
            AssistantMessage(
                content="",
                tool_calls=[ToolCall("t1", "write_file", json.dumps({"path": "x.txt", "content": "data"}))],
            ),
            AssistantMessage(content="done"),
        ]
    )
    tools = build_tools(tmp_path)
    messages = [{"role": "user", "content": "go"}]
    events = []

    msg = run_agent_turn(
        messages,
        provider,
        "m",
        tools,
        on_tool_event=lambda k, p: events.append(k),
        approve=lambda t, a: True,
    )
    assert msg.content == "done"
    assert (tmp_path / "x.txt").read_text() == "data"
    assert provider.calls == 2
    assert events == ["tool_start", "tool_end"]
    # history: user, assistant(tool_call), tool result, assistant(final)
    assert messages[1]["tool_calls"][0]["function"]["name"] == "write_file"
    assert messages[2]["role"] == "tool"


def test_denied_tool_call(tmp_path):
    provider = ScriptedProvider(
        [
            AssistantMessage(
                content="",
                tool_calls=[ToolCall("t1", "run_shell", json.dumps({"command": "rm -rf /"}))],
            ),
            AssistantMessage(content="ok then"),
        ]
    )
    tools = build_tools(tmp_path)
    messages = [{"role": "user", "content": "go"}]

    run_agent_turn(
        messages, provider, "m", tools, approve=lambda t, a: False
    )
    tool_result = messages[2]
    assert "denied" in tool_result["content"].lower()
    assert tool_result["is_error"] is True


def test_tool_whitelist(tmp_path):
    provider = ScriptedProvider(
        [
            AssistantMessage(
                content="",
                tool_calls=[ToolCall("t1", "run_shell", json.dumps({"command": "echo hi"}))],
            ),
            AssistantMessage(content="done"),
        ]
    )
    tools = build_tools(tmp_path)
    messages = [{"role": "user", "content": "go"}]
    run_agent_turn(
        messages, provider, "m", tools,
        approve=lambda t, a: True,
        enabled_tools=["read_file"],  # run_shell not enabled
    )
    assert "Unknown tool" in messages[2]["content"]
