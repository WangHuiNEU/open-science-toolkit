"""大脑封装：连接 OpenAI 兼容端点。

阶段 0 用裸 openai 客户端验证端点可用。
到 OpenHands 接入阶段，这层会换成 OpenHands 的 `LLM` 类（底层 LiteLLM），
但对外接口（chat / ping）保持不变，方便切换后端。

凭据一律从环境变量读，绝不硬编码：
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class Brain:
    """最小 OpenAI 兼容大脑封装。"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url or os.environ["LLM_BASE_URL"]
        self.model = model or os.environ["LLM_MODEL"]
        api_key = api_key or os.environ["LLM_API_KEY"]
        self._client = OpenAI(api_key=api_key, base_url=self.base_url)

    def chat(self, message: str, *, system: str | None = None, max_tokens: int = 512) -> str:
        """发一条消息，返回回复文本。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def ping(self) -> str:
        """连通性自检：应返回含 'pong' 的字符串。"""
        return self.chat("reply with the single word: pong", max_tokens=20)


if __name__ == "__main__":
    brain = Brain()
    print("endpoint:", brain.base_url)
    print("model   :", brain.model)
    print("ping    :", repr(brain.ping()))
