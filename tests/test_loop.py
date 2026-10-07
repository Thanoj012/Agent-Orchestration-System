from app.agents.loop import parse_reply, run_tool_loop
from app.agents.prompts import build_system
from app.tools.base import Tool


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, messages):
        self.calls.append([dict(m) for m in messages])
        return self.replies.pop(0)


ECHO = Tool("echo", "echoes", '{"text": ""}', lambda a: "echo:" + str(a.get("text")))


def test_parse_tool_and_final():
    assert parse_reply('TOOL: {"tool": "echo", "input": {"text": "hi"}}') == ("tool", "echo", {"text": "hi"})
    assert parse_reply("FINAL:\nThe answer.\nSecond line.") == ("final", "The answer.\nSecond line.")
    assert parse_reply("Just plain text") == ("final", "Just plain text")
    assert parse_reply('Let me check.\nTOOL: {"tool": "echo"}')[0] == "tool"
    assert parse_reply("FINAL:\nUse this: TOOL: {} is not a call")[0] == "final"


def test_parse_invalid():
    assert parse_reply("TOOL: not json")[0] == "invalid"
    assert parse_reply('TOOL: {"input": {}}')[0] == "invalid"
    assert parse_reply("FINAL:")[0] == "invalid"
    assert parse_reply("TOOL: {")[0] == "invalid"


def test_loop_calls_tool_then_finishes():
    llm = FakeLLM(['TOOL: {"tool": "echo", "input": {"text": "x"}}', "FINAL:\ndone"])
    seen = []
    result = run_tool_loop(llm, "sys", "task", {"echo": ECHO}, on_tool=lambda n, a, o: seen.append((n, o)))
    assert result.output == "done" and result.tool_calls == 1
    assert seen == [("echo", "echo:x")]
    second_call = llm.calls[1]
    assert second_call[-1]["role"] == "user" and "echo:x" in second_call[-1]["content"]
    assert [m["role"] for m in second_call] == ["user", "assistant", "user"]  # strictly alternating


def test_unknown_tool_and_invalid_reply_are_recoverable():
    llm = FakeLLM(['TOOL: {"tool": "nope"}', "TOOL: garbage", "FINAL:\nok"])
    result = run_tool_loop(llm, "sys", "task", {"echo": ECHO})
    assert result.output == "ok" and result.tool_calls == 0
    assert "unknown tool" in llm.calls[1][-1]["content"]
    assert "invalid" in llm.calls[2][-1]["content"]


def test_step_limit_forces_a_final_answer():
    calls = ['TOOL: {"tool": "echo", "input": {}}'] * 3 + ["FINAL:\nforced"]
    result = run_tool_loop(FakeLLM(calls), "sys", "task", {"echo": ECHO}, max_steps=3)
    assert result.output == "forced" and result.tool_calls == 3


def test_system_prompt_lists_only_given_tools():
    assert "echo: echoes" in build_system("Role.", {"echo": ECHO})
    assert "You have no tools" in build_system("Role.", {})
