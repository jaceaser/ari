"""
Real integration stress test — 50-turn conversation against a live API.

Skipped automatically when the API is unreachable or JWT_SECRET is not set.

Run against local dev server:
    JWT_SECRET=<secret> pytest tests/test_stress_integration.py -v -s

Run against production:
    API_BASE_URL=https://reilabs-ari-api.azurewebsites.net \\
    JWT_SECRET=<secret> \\
    pytest tests/test_stress_integration.py -v -s

Environment variables:
    API_BASE_URL         Target API (default: http://localhost:8000)
    JWT_SECRET           Required — must match the running server's secret
    STRESS_USER_ID       UUID to use as user identity (default: generated)
    STRESS_USER_EMAIL    Email in the JWT (default: stress-test@example.com)
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import time
import uuid

import httpx
import pytest

# ── Config ───────────────────────────────────────────────────────────────────

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
JWT_SECRET = os.getenv("JWT_SECRET", "")
STRESS_USER_ID = os.getenv("STRESS_USER_ID", str(uuid.uuid4()))
STRESS_USER_EMAIL = os.getenv("STRESS_USER_EMAIL", "stress-test@example.com")

# Per-turn timeout: 5 minutes (covers orchestration + long streaming response)
TURN_TIMEOUT = float(os.getenv("STRESS_TURN_TIMEOUT", "300"))

# ── 50 prompts ────────────────────────────────────────────────────────────────

PROMPTS: list[str] = [
    # Basics
    "What is wholesaling real estate?",
    "How do I find motivated sellers in my area?",
    "What does ARV mean and how do I calculate it?",
    "What is the 70% rule for fix-and-flip deals?",
    "How do I analyze a rental property for cash flow?",
    # Strategies
    "What is a subject-to deal in real estate?",
    "How do I execute a BRRRR deal from start to finish?",
    "What is seller financing and how do I structure it?",
    "How does a double closing work?",
    "What is a novation agreement and when would I use one instead of a standard assignment?",
    # Lead gen
    "How do I build a buyers list from scratch for wholesaling?",
    "What are the best ways to market to absentee owners?",
    "How do I find pre-foreclosure properties before they hit the MLS?",
    "What is a lis pendens and why does it matter for investors?",
    "How do I find off-market deals without using the MLS?",
    # Finance
    "What is a hard money loan and when should I use one?",
    "What is a cap rate and how do I use it to value commercial property?",
    "How do I use a self-directed IRA to invest in real estate?",
    "What are the tax benefits of owning rental properties?",
    "What is a land contract and how does it differ from a mortgage?",
    # Deals & analysis
    "How do I estimate repair costs on a distressed property?",
    "What is the difference between a short sale and a foreclosure?",
    "How do I negotiate with motivated sellers to get a below-market price?",
    "What due diligence should I do before closing on a fix-and-flip?",
    "What is the difference between a purchase and sale agreement and an assignment contract?",
    # Advanced
    "How do I evaluate a mobile home park as an investment?",
    "How do I scale from one rental property to a portfolio of ten?",
    "What is equity stripping and why should investors be aware of it?",
    "How do I wholesale a deal if I don't have a buyers list yet?",
    "What is driving down home prices in certain markets right now?",
    # Contracts & legal
    "What clauses should every wholesale contract include?",
    "How do I structure a lease-option agreement for a motivated seller?",
    "What is a deed in lieu of foreclosure and when would a seller agree to it?",
    "How do I handle title issues discovered during due diligence?",
    "What is a quiet title action and when do I need one?",
    # Market analysis
    "How do I run comps for a property in a rural area with few sales?",
    "What makes a neighborhood a strong rental market vs a flip market?",
    "How does interest rate movement affect my exit strategies as an investor?",
    "What market indicators signal a good time to buy distressed properties?",
    "How do I evaluate a ZIP code for wholesale deal volume?",
    # Operations & scaling
    "How do I build a virtual wholesaling business in a market I've never visited?",
    "What CRM should I use to manage leads as a wholesaler?",
    "How do I structure my real estate investing business for asset protection?",
    "What is a JV agreement and how do I structure one with a money partner?",
    "How do I hire and train a disposition manager?",
    # Follow-ups that build on prior context
    "Based on everything we've discussed, what is the single most important skill for a new wholesaler to develop?",
    "You mentioned several financing strategies — which works best for someone with no cash and no credit?",
    "Given the market conditions you described, is now a good time to start wholesaling or should I wait?",
    "What is the biggest mistake you see new real estate investors make with all of these strategies?",
    "Can you give me a step-by-step action plan to close my first wholesale deal in the next 30 days?",
]

assert len(PROMPTS) == 50, f"Expected 50 prompts, got {len(PROMPTS)}"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_jwt() -> str:
    import jwt as pyjwt

    now = datetime.datetime.now(datetime.timezone.utc)
    return pyjwt.encode(
        {
            "sub": STRESS_USER_ID,
            "email": STRESS_USER_EMAIL,
            "iat": now,
            "exp": now + datetime.timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _read_sse_stream(
    response: httpx.Response,
) -> tuple[str, bool, bool]:
    """
    Consume an SSE streaming response.

    Returns
    -------
    text : str
        Full concatenated assistant text.
    done : bool
        True when ``[DONE]`` was received.
    truncated : bool
        True when the backend injected a token-limit notice.
    """
    text_parts: list[str] = []
    done = False
    buffer = ""

    async for raw_bytes in response.aiter_bytes():
        buffer += raw_bytes.decode("utf-8", errors="replace")
        while True:
            lf = buffer.find("\n\n")
            crlf = buffer.find("\r\n\r\n")
            if lf == -1 and crlf == -1:
                break
            if crlf != -1 and (lf == -1 or crlf < lf):
                event, buffer = buffer[:crlf], buffer[crlf + 4:]
            else:
                event, buffer = buffer[:lf], buffer[lf + 2:]

            for line in event.splitlines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    content = (choice.get("delta") or {}).get("content")
                    if content:
                        text_parts.append(content)

    full_text = "".join(text_parts)
    truncated = "length limit" in full_text.lower() or "cut off" in full_text.lower()
    return full_text, done, truncated


def _skip_if_unavailable() -> None:
    """Skip the test with a clear message if prerequisites are not met."""
    if not JWT_SECRET:
        pytest.skip("JWT_SECRET not set — skipping integration stress test")

    try:
        import httpx as _httpx
        with _httpx.Client(timeout=5) as c:
            c.get(f"{API_BASE_URL}/health")
    except Exception:
        pytest.skip(f"API not reachable at {API_BASE_URL} — skipping integration stress test")


# ── Test ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_50_turn_real_streaming_conversation():
    """
    Send 50 real estate prompts to the live API over a single session,
    reading the actual SSE stream for each turn.

    Asserts per turn:
      - HTTP 200
      - SSE stream ends with [DONE]
      - Non-empty response text
      - No token-limit truncation notice injected by the backend

    Prints a timing/length summary for each turn so you can spot slow
    or short responses at a glance.
    """
    _skip_if_unavailable()

    jwt = _make_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    }

    print(f"\n\nStress test → {API_BASE_URL}")
    print(f"User: {STRESS_USER_EMAIL} ({STRESS_USER_ID})")

    async with httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=httpx.Timeout(TURN_TIMEOUT, connect=10),
    ) as client:
        # Create session
        resp = await client.post("/sessions", headers=headers)
        assert resp.status_code == 201, f"Failed to create session: {resp.status_code} {resp.text}"
        session_id = resp.json()["id"]
        print(f"Session: {session_id}\n")
        print(f"{'Turn':>4}  {'Time':>6}  {'Chars':>6}  {'Done':>5}  {'Trunc':>5}  Preview")
        print("-" * 72)

        failures: list[str] = []

        for turn, prompt in enumerate(PROMPTS, start=1):
            t0 = time.monotonic()
            try:
                async with client.stream(
                    "POST",
                    f"/sessions/{session_id}/messages",
                    json={"content": prompt},
                    headers=headers,
                ) as stream_resp:
                    if stream_resp.status_code != 200:
                        body = await stream_resp.aread()
                        failures.append(
                            f"Turn {turn}: HTTP {stream_resp.status_code} — {body.decode()[:200]}"
                        )
                        print(f"{turn:>4}  {'—':>6}  {'—':>6}  {'—':>5}  {'—':>5}  HTTP {stream_resp.status_code}")
                        continue

                    text, done, truncated = await _read_sse_stream(stream_resp)

            except Exception as exc:
                elapsed = time.monotonic() - t0
                failures.append(f"Turn {turn}: exception after {elapsed:.1f}s — {exc}")
                print(f"{turn:>4}  {elapsed:>5.1f}s  {'—':>6}  {'—':>5}  {'—':>5}  ERROR: {exc}")
                continue

            elapsed = time.monotonic() - t0
            preview = text[:60].replace("\n", " ")
            print(
                f"{turn:>4}  {elapsed:>5.1f}s  {len(text):>6}  {str(done):>5}  {str(truncated):>5}  {preview}"
            )

            if not done:
                failures.append(f"Turn {turn}: [DONE] not received")
            if not text:
                failures.append(f"Turn {turn}: empty response")
            if truncated:
                failures.append(
                    f"Turn {turn}: response hit token limit (truncation notice present)"
                )

        print("-" * 72)
        print(f"\n{len(PROMPTS) - len(failures)}/{len(PROMPTS)} turns passed\n")

        if failures:
            pytest.fail("Stress test failures:\n" + "\n".join(f"  • {f}" for f in failures))
