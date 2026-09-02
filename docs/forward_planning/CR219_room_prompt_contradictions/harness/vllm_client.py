"""Blocking OpenAI-compatible client for the on-prem vLLM serve, LAN-direct.

Why not `LLMGateway`: the gateway is async, streams, and resolves its provider
from env. This harness needs one blocking call with the model identity pinned to
what the SERVE reports, plus the ability to flip per-request thinking for the R48
A/B. Everything the gateway does that matters to prompt fidelity happens in
`build_room_messages`, which the runner calls directly — this file only carries
bytes to the server and back.

Model identity is read from `/v1/models` `root`, never from the `id` alias. The
alias `ami-llm` was reused across the 2026-08-28 model swap and now names a
DIFFERENT model than it did before, so any run banked under that name is
unattributable. `identity()` is what goes into the scored JSON.

No credential is read, printed, or stored: the LAN serve is unauthenticated and
this client sends no Authorization header.
"""
import json
import time
import urllib.request

DEFAULT_BASE_URL = "http://192.168.20.74:8048"


class VLLMError(RuntimeError):
    pass


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class VLLMClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._identity: dict | None = None

    def identity(self) -> dict:
        """{alias, root, max_model_len} straight off the serve.

        `root` is the authority. Cached per client so a long run does not
        re-ask, but fetched at least once per run so a scored JSON can never
        claim a model the serve was not actually running.
        """
        if self._identity is None:
            with urllib.request.urlopen(f"{self.base_url}/v1/models", timeout=30) as r:
                data = json.loads(r.read().decode())["data"]
            if not data:
                raise VLLMError(f"{self.base_url}/v1/models returned no models")
            m = data[0]
            self._identity = {
                "alias": m.get("id"),
                "root": m.get("root"),
                "max_model_len": m.get("max_model_len"),
                "base_url": self.base_url,
                "aliases_served": sorted(x.get("id") for x in data),
            }
        return self._identity

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        temperature: float = 1.0,
        thinking: bool = False,
        reasoning_effort: str | None = None,
    ) -> dict:
        """One completion. Returns answer + the fields a scorer needs.

        `thinking=True` sends `chat_template_kwargs={"enable_thinking": true}` —
        the form this build actually honours (R48 probe, 2026-09-02: it moves
        `usage.completion_tokens_details.reasoning_tokens` off zero; a top-level
        `enable_thinking` and a `chat_template_kwargs.thinking` do NOT).

        `reasoning_tokens` is returned on EVERY call, thinking on or off, so an
        arm that claims thinking-on can be checked rather than believed.
        """
        body: dict = {
            "model": self.identity()["alias"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if thinking:
            body["chat_template_kwargs"] = {"enable_thinking": True}
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort

        t0 = time.time()
        try:
            data = _post(f"{self.base_url}/v1/chat/completions", body, self.timeout)
        except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
            # CR040 degrade loudly: an outage must not look like a bad answer.
            return {
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - t0, 1),
            }
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        return {
            "answer": msg.get("content") or "",
            # Separated reasoning channel when the serve emits one; this build
            # inlines thinking into `content` instead, so it is normally None.
            "reasoning_content": msg.get("reasoning_content"),
            "finish": choice.get("finish_reason"),
            "tok_prompt": usage.get("prompt_tokens"),
            "tok_out": usage.get("completion_tokens"),
            "tok_reasoning": details.get("reasoning_tokens"),
            "elapsed_s": round(time.time() - t0, 1),
        }
