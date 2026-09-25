from epilepticcli.providers.anthropic import _convert_messages, _convert_tools
from epilepticcli.providers.base import ToolCall
from epilepticcli.providers.demo import DemoProvider


def test_anthropic_message_conversion():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "ok",
            "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "a"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "result"},
    ]
    system, out = _convert_messages(msgs)
    assert system == "sys"
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1]["role"] == "assistant"
    assert out[1]["content"][1]["type"] == "tool_use"
    assert out[2]["role"] == "user"
    assert out[2]["content"][0]["type"] == "tool_result"


def test_anthropic_tool_schema_conversion():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "f",
                "description": "d",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    out = _convert_tools(tools)
    assert out[0]["name"] == "f"
    assert out[0]["input_schema"]["type"] == "object"


def test_demo_provider_streams():
    chunks = []
    p = DemoProvider()
    msg = p.stream_chat(
        [{"role": "user", "content": "hi"}], "demo", on_delta=chunks.append
    )
    assert "".join(chunks) == msg.content
    assert msg.usage.input_tokens >= 0


def test_assistant_wire_roundtrip():
    from epilepticcli.providers.base import AssistantMessage

    m = AssistantMessage(content="x", tool_calls=[ToolCall("i", "n", "{}")])
    wire = m.to_wire()
    assert wire["role"] == "assistant"
    assert wire["tool_calls"][0]["function"]["name"] == "n"
