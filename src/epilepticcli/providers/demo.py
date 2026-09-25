"""Offline demo provider - streams a canned reply, no API key needed.

Useful for trying the UI, scripting tests, and demos:
    epileptic --provider demo --model demo
"""

from __future__ import annotations

import itertools
import time
from typing import Any

from epilepticcli.providers.base import AssistantMessage, OnDelta, Provider, ToolSpec, Usage

DEMO_REPLY = """\
Here is a simulated answer from the built-in **demo** provider.

- Streaming works
- `inline code` and code blocks render
- Markdown formatting is live

```python
def hello() -> str:
    return "epileptic"
```

Connect a real provider in `~/.epilepticcli/config.yaml` to talk to an actual model.
"""

WORD_DELAY = 0.008


class DemoProvider(Provider):
    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_delta: OnDelta | None = None,
    ) -> AssistantMessage:
        last_user = next(
            (m for m in reversed(messages) if m.get("role") == "user"), None
        )
        prefix = ""
        if last_user and isinstance(last_user.get("content"), str):
            prefix = f"> You said: *{last_user['content'][:120]}*\n\n"
        reply = prefix + DEMO_REPLY
        words = reply.split(" ")
        for i, w in enumerate(words):
            chunk = w + (" " if i < len(words) - 1 else "")
            if on_delta:
                on_delta(chunk)
            time.sleep(WORD_DELAY)
        n_in = sum(len(str(m.get("content") or "")) for m in messages) // 4
        return AssistantMessage(
            content=reply,
            usage=Usage(input_tokens=n_in, output_tokens=len(reply) // 4),
        )

    def list_models(self) -> list[str]:
        return list(itertools.islice(["demo"], 1))
