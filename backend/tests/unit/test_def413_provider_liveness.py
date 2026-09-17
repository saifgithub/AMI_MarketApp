"""DEF413 — "configured" and "answering" are two facts and must show as two.

`has_real_provider()` is `any(name != "mock" for name in self._providers)`: a
dict-key test over what registered at STARTUP. A provider registers when its
settings are present, never when it answers. Measured 2026-09-17: the vLLM host
`192.168.20.74` lost its route — 100% packet loss and connection refused from
the Mac, from melehost and from inside `ami_api_alpha`, with the container's own
logs carrying `No route to host` — while `/v1/llm/status` returned
`has_real_provider: true` and `/v1/ready` returned `ready: true,
failed_probes: []`. Three operator surfaces read healthy with no model behind
them, and a promotion passed its smoke check on them.

The fix does not add a health probe. `/v1/ready` is polled often and a readiness
endpoint that fans out to a GPU host on every hit is its own defect. Instead the
gateway records the transport outcome it ALREADY sees on every call, and that
recorded fact is surfaced and gated on.

Three properties, one per class below.

**`failed` is loud.** A provider we have positively seen fail fails the gating
probe — that is the DEF413 scenario, and the whole point.

**`unknown` is not failure.** A container that has served no traffic has no
evidence. Failing on absence of evidence would red every cold start before it
answered one request, so `unknown` passes while remaining visibly distinct from
`ok`. It must equally never be read AS healthy, which is DEF413 restated.

**Transport, not quality.** A provider that answers emptily is reachable. Only a
failure to complete the exchange counts, because the question is "is anything
there" — conflating the two reports a working host as dead.
"""

from __future__ import annotations

import pytest

from app.services.llm_gateway import LLMGateway
from app.services.readiness import _probe_llm


@pytest.fixture
def gateway() -> LLMGateway:
    return LLMGateway()


class TestAFailedProviderIsCaught:
    def test_the_def413_scenario_fails_the_gating_probe(self, gateway, monkeypatch):
        """Registered, resolves to vllm, and the last call did not complete."""
        monkeypatch.setattr(
            "app.services.llm_gateway.get_llm_gateway", lambda: gateway
        )
        gateway._providers["vllm"] = object()  # registered, as config makes it
        gateway.note_transport_outcome(
            "vllm", ok=False, error="ConnectError: All connection attempts failed"
        )

        probe = _probe_llm("staging")

        assert probe.ok is False, (
            "a provider the gateway has positively seen fail must not read ready "
            "— this is exactly DEF413"
        )
        assert probe.gating is True
        assert probe.detail["has_real_provider"] is True, (
            "the config fact is unchanged and still true; it is simply no longer "
            "the whole answer"
        )
        assert probe.detail["liveness"] == "failed"
        assert "connection" in probe.detail["liveness_error"].lower()

    def test_status_reports_both_facts_separately(self, gateway):
        gateway._providers["vllm"] = object()
        gateway.note_transport_outcome("vllm", ok=False, error="No route to host")

        status = gateway.status()

        assert status["has_real_provider"] is True
        assert status["active_provider_liveness"]["state"] == "failed"
        assert status["active_provider_liveness"]["error"] == "No route to host"
        assert status["active_provider_liveness"]["as_of"] is not None

    def test_a_recovered_provider_goes_green_again(self, gateway, monkeypatch):
        """The record is last-outcome, not a latch — recovery must clear it."""
        monkeypatch.setattr(
            "app.services.llm_gateway.get_llm_gateway", lambda: gateway
        )
        gateway._providers["vllm"] = object()
        gateway.note_transport_outcome("vllm", ok=False, error="boom")
        assert _probe_llm("staging").ok is False

        gateway.note_transport_outcome("vllm", ok=True)

        probe = _probe_llm("staging")
        assert probe.ok is True
        assert probe.detail["liveness"] == "ok"
        assert probe.detail["liveness_error"] is None, (
            "a stale error surviving recovery would make the surface lie in the "
            "other direction"
        )


class TestUnknownIsNotFailure:
    def test_a_cold_container_still_reads_ready(self, gateway, monkeypatch):
        """No call yet is no evidence — not evidence of absence."""
        monkeypatch.setattr(
            "app.services.llm_gateway.get_llm_gateway", lambda: gateway
        )
        gateway._providers["vllm"] = object()

        probe = _probe_llm("staging")

        assert probe.ok is True, (
            "failing on absence of evidence would red every cold start before it "
            "served one request"
        )
        assert probe.detail["liveness"] == "unknown"

    def test_unknown_is_visibly_distinct_from_ok(self, gateway):
        gateway._providers["vllm"] = object()
        assert gateway.provider_liveness("vllm")["state"] == "unknown"

        gateway.note_transport_outcome("vllm", ok=True)
        assert gateway.provider_liveness("vllm")["state"] == "ok"

    def test_unknown_carries_no_timestamp(self, gateway):
        """An `as_of` on a state nobody measured would invent a measurement."""
        assert gateway.provider_liveness("vllm")["as_of"] is None

    def test_mock_only_still_fails_the_probe(self, gateway, monkeypatch):
        """DEF059's original catch must survive the widening."""
        monkeypatch.setattr(
            "app.services.llm_gateway.get_llm_gateway", lambda: gateway
        )

        probe = _probe_llm("staging")

        assert probe.ok is False
        assert probe.detail["has_real_provider"] is False


class TestTransportNotQuality:
    def test_an_empty_but_clean_answer_is_reachable(self, gateway):
        """A model with nothing to say is not an unreachable model."""
        gateway.note_transport_outcome("vllm", ok=True, error=None)
        assert gateway.provider_liveness("vllm")["state"] == "ok"

    def test_an_error_passed_with_ok_true_does_not_poison_the_record(self, gateway):
        """`ok` is the judgement; a stray error string must not override it."""
        gateway.note_transport_outcome("vllm", ok=True, error="ignored")
        live = gateway.provider_liveness("vllm")
        assert live["state"] == "ok"
        assert live["error"] is None

    def test_providers_are_tracked_independently(self, gateway):
        """One dead provider must not condemn another that is answering."""
        gateway.note_transport_outcome("vllm", ok=False, error="down")
        gateway.note_transport_outcome("kimi", ok=True)

        assert gateway.provider_liveness("vllm")["state"] == "failed"
        assert gateway.provider_liveness("kimi")["state"] == "ok"

    def test_liveness_defaults_to_the_active_provider(self, gateway):
        gateway._providers["vllm"] = object()
        gateway.note_transport_outcome("vllm", ok=False, error="down")

        assert gateway.provider_liveness()["provider"] == "vllm"
        assert gateway.provider_liveness()["state"] == "failed"


class TestTheRealCallPathRecordsIt:
    """The recording must happen on the gateway's OWN call path.

    Everything above drives `note_transport_outcome` directly, which proves the
    record works but not that anything calls it — the DEF357 shape, where a
    function had 21 call sites and every one was a test. A mutation making the
    `finally` block record `ok=True` unconditionally survived the first version
    of this file, so these drive `stream_chat` end to end.
    """

    @staticmethod
    def _gateway_with(monkeypatch, provider):
        gw = LLMGateway()
        gw._providers["vllm"] = provider
        monkeypatch.setattr(gw, "_pick_provider", lambda *a, **k: provider)
        # Imported inside `stream_chat` from `app.services.audit`, so that is
        # where it must be patched — the gateway module has no such attribute.
        monkeypatch.setattr(
            "app.services.audit.record_llm_call", lambda **k: None
        )
        return gw

    @pytest.mark.asyncio
    async def test_a_raising_provider_is_recorded_failed(self, monkeypatch):
        class Boom:
            name = "vllm"
            supported_constraints: set[str] = set()

            async def stream_chat(self, **kwargs):
                raise ConnectionError("All connection attempts failed")
                yield  # pragma: no cover - generator shape only

        gw = self._gateway_with(monkeypatch, Boom())

        with pytest.raises(ConnectionError):
            async for _ in gw.stream_chat(
                system_prompt="s",
                messages=[],
                model_tier="cheap",
                locale="en",
            ):
                pass

        live = gw.provider_liveness("vllm")
        assert live["state"] == "failed", (
            "the exception path must reach the record, or DEF413's own scenario "
            "goes unrecorded"
        )
        assert "All connection attempts failed" in live["error"]

    @pytest.mark.asyncio
    async def test_an_inband_stream_error_is_recorded_failed(self, monkeypatch):
        """DEF376's frame never raises — and it still means unreachable."""

        class InBand:
            name = "vllm"
            supported_constraints: set[str] = set()

            async def stream_chat(self, **kwargs):
                kwargs["meta"]["stream_error"] = "upstream returned error frame"
                return
                yield  # pragma: no cover - generator shape only

        gw = self._gateway_with(monkeypatch, InBand())

        async for _ in gw.stream_chat(
            system_prompt="s", messages=[], model_tier="cheap", locale="en"
        ):
            pass

        assert gw.provider_liveness("vllm")["state"] == "failed"

    @pytest.mark.asyncio
    async def test_a_clean_call_is_recorded_ok(self, monkeypatch):
        class Fine:
            name = "vllm"
            supported_constraints: set[str] = set()

            async def stream_chat(self, **kwargs):
                yield "hello"

        gw = self._gateway_with(monkeypatch, Fine())

        async for _ in gw.stream_chat(
            system_prompt="s", messages=[], model_tier="cheap", locale="en"
        ):
            pass

        live = gw.provider_liveness("vllm")
        assert live["state"] == "ok"
        assert live["error"] is None


class TestTheProbeMakesNoCall:
    def test_no_http_client_is_touched_by_status_or_the_probe(
        self, gateway, monkeypatch
    ):
        """The fix must not turn a polled endpoint into a fan-out to the GPU host.

        `/v1/ready` is hit by Cloudflare and by every postflight; a readiness
        check that issues a provider request on each poll is its own defect.
        """
        monkeypatch.setattr(
            "app.services.llm_gateway.get_llm_gateway", lambda: gateway
        )
        gateway._providers["vllm"] = object()

        def explode(*a, **k):  # pragma: no cover - must never run
            raise AssertionError("the readiness path made a network call")

        monkeypatch.setattr("httpx.Client.request", explode)
        monkeypatch.setattr("httpx.AsyncClient.request", explode)

        _probe_llm("staging")
        gateway.status()
