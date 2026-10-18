from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from complaint_triage.rag.llm import CachedModel, GeminiModel, QuotaExceededError, QuotaGuard

SCHEMA: dict[str, Any] = {"type": "OBJECT"}


class Clock:
    def __init__(self, start: float) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


# 18 octobre 2026, 12 h UTC (5 h du matin en Californie).
NOON_UTC = 1792324800.0


def guard(tmp_path: Path, clock: Clock, daily: int = 3, minute: int = 2) -> QuotaGuard:
    return QuotaGuard(tmp_path / "quota.json", daily, minute, clock=clock, sleep=clock.sleep)


def test_the_daily_cap_blocks_the_call_before_sending_it(tmp_path: Path) -> None:
    clock = Clock(NOON_UTC)
    quota = guard(tmp_path, clock)
    for _ in range(3):
        quota.acquire()
        clock.now += 61

    with pytest.raises(QuotaExceededError, match="aucun appel envoyé"):
        quota.acquire()


def test_the_counter_survives_a_restart(tmp_path: Path) -> None:
    clock = Clock(NOON_UTC)
    guard(tmp_path, clock).acquire()

    assert guard(tmp_path, clock).used_today() == 1


def test_the_counter_resets_at_midnight_pacific_time(tmp_path: Path) -> None:
    clock = Clock(NOON_UTC)
    quota = guard(tmp_path, clock, daily=1)
    quota.acquire()

    clock.now += 20 * 3600  # le lendemain, heure de Californie
    quota.acquire()

    assert quota.used_today() == 1


def test_the_minute_cap_waits_instead_of_exceeding(tmp_path: Path) -> None:
    clock = Clock(NOON_UTC)
    quota = guard(tmp_path, clock, daily=10, minute=2)

    quota.acquire()
    quota.acquire()
    quota.acquire()

    assert clock.slept and clock.slept[0] > 59


class CountingModel:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.calls += 1
        return '{"answerable": false}'


def test_a_cached_answer_costs_no_call(tmp_path: Path) -> None:
    inner = CountingModel()
    model = CachedModel(inner, tmp_path / "cache")

    first = model.generate("system", "prompt", SCHEMA)
    second = model.generate("system", "prompt", SCHEMA)
    model.generate("system", "another prompt", SCHEMA)

    assert first == second
    assert inner.calls == 2
    assert model.is_cached("system", "prompt", SCHEMA)
    assert not model.is_cached("system", "never asked", SCHEMA)


def gemini(tmp_path: Path, post: Any) -> GeminiModel:
    clock = Clock(NOON_UTC)
    return GeminiModel(
        guard(tmp_path, clock, daily=5, minute=5), model="m", api_key="secret", post=post
    )


def test_the_key_travels_in_a_header_not_in_the_url(tmp_path: Path) -> None:
    seen: list[urllib.request.Request] = []

    def post(request: urllib.request.Request, timeout: float) -> bytes:
        seen.append(request)
        reply = {"candidates": [{"content": {"parts": [{"text": '{"answerable": true}'}]}}]}
        return json.dumps(reply).encode()

    text = gemini(tmp_path, post).generate("system", "prompt", SCHEMA)

    assert text == '{"answerable": true}'
    assert "secret" not in seen[0].full_url
    assert seen[0].get_header("X-goog-api-key") == "secret"


def test_a_429_stops_everything_without_retrying(tmp_path: Path) -> None:
    calls = 0

    def post(request: urllib.request.Request, timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", None, io.BytesIO())  # type: ignore[arg-type]

    with pytest.raises(QuotaExceededError, match="429"):
        gemini(tmp_path, post).generate("system", "prompt", SCHEMA)
    assert calls == 1


def test_a_blocked_answer_comes_back_empty(tmp_path: Path) -> None:
    def post(request: urllib.request.Request, timeout: float) -> bytes:
        return b'{"promptFeedback": {"blockReason": "SAFETY"}}'

    assert gemini(tmp_path, post).generate("system", "prompt", SCHEMA) == ""


def test_missing_settings_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    with pytest.raises(ValueError, match="GEMINI"):
        GeminiModel(guard(tmp_path, Clock(NOON_UTC)))
