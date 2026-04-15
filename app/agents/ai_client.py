"""
LLM clients for structured trading decisions (Anthropic Claude or OpenAI Chat Completions).

Responsibilities:
- Strict system prompt → JSON-only output matching AgentOutput.
- Lazy imports so missing SDKs do not break startup for unused providers.
- On ANY failure: return SKIP (never raises to callers).

Keys: AI_API_KEY (Anthropic), OPENAI_API_KEY (OpenAI). Provider via AI_PROVIDER.
"""
import json

from app.agents.schemas import AgentDecision, AgentInput, AgentOutput
from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# ─── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a crypto trading signal synthesizer embedded in a paper-trading bot.
Your job: analyze multiple indicators (and any optional news_headlines in the JSON) and produce ONE consolidated decision.

analyst_summaries (when present):
  - These are server-side, deterministic summaries (signal agreement, market_context snapshot, headline lexicon scan).
  - They are hints, not ground truth — headlines can be stale or clickbait; lexicon can miss nuance.
  - Use them to structure your reasoning, but weigh raw `signals` and `news_headlines` directly when they disagree with a summary.

Definitions:
  ENTER       — signals align with sufficient confidence; proceed with trade
  SKIP        — signals conflict, confidence too low, or risk/reward unfavorable
  REDUCE_SIZE — signals lean in one direction but conviction is weak; enter smaller

News / external data:
  - news_headlines (if present) are a third-party snapshot fetched by the server — NOT live web search.
  - They may be stale, biased, or irrelevant; use them only as soft context alongside price-based signals.
  - Never treat headlines alone as sufficient for ENTER; conflicting or unverified news → lean SKIP.

Hard rules:
  - You are NOT the final risk authority. A RiskManager enforces hard capital limits after you.
  - Prefer SKIP over ENTER when uncertain — preserving capital is paramount.
  - Your reason MUST explain the specific signals (and, if used, which headline themes) that drove your decision.

Respond with VALID JSON ONLY — no markdown, no extra text:
{"decision": "ENTER"|"SKIP"|"REDUCE_SIZE", "confidence": 0.0–1.0, "reason": "explanation"}"""

_USER_TEMPLATE = """\
Analyze the following signal bundle and decide:

{input_json}

Respond with JSON only."""


# ─── Client ───────────────────────────────────────────────────────────────────


class AIDecisionClient:
    """
    Wraps Anthropic or OpenAI for trading decisions.

    Fallback contract: any failure → SKIP (never raises, never blocks orders).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = settings.ai_provider.strip().lower()
        self._enabled = self._compute_enabled()
        if not self._enabled and settings.ai_enabled:
            log.warning(
                "AI decisions disabled — check AI_PROVIDER and matching API key "
                "(anthropic → AI_API_KEY, openai → OPENAI_API_KEY)"
            )

    def _compute_enabled(self) -> bool:
        if not self._settings.ai_enabled:
            return False
        if self._provider == "openai":
            return bool(self._settings.openai_api_key)
        if self._provider in ("anthropic", "claude"):
            return bool(self._settings.ai_api_key)
        log.error("Unknown AI_PROVIDER=%r — use anthropic or openai", self._provider)
        return False

    async def decide(self, agent_input: AgentInput) -> AgentOutput:
        """Return an AgentOutput. Never raises — falls back to SKIP on any error."""
        if not self._enabled:
            return _skip(
                "AI not configured — set AI_PROVIDER and the matching API key "
                "(OPENAI_API_KEY for openai, AI_API_KEY for anthropic)"
            )
        try:
            if self._provider == "openai":
                return await self._call_openai(agent_input)
            return await self._call_claude(agent_input)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "AI decision error (%s: %s) — returning SKIP to preserve capital",
                type(exc).__name__,
                exc,
            )
            return _skip(
                f"AI service unavailable ({type(exc).__name__}) — skipping to preserve capital"
            )

    async def _call_claude(self, agent_input: AgentInput) -> AgentOutput:
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic(
            api_key=self._settings.ai_api_key,
            timeout=self._settings.ai_timeout,
        )
        user_content = _USER_TEMPLATE.format(
            input_json=agent_input.model_dump_json(indent=2)
        )
        message = await client.messages.create(
            model=self._settings.ai_model,
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = message.content[0].text.strip()
        return _parse_and_log(agent_input.symbol, raw)

    async def _call_openai(self, agent_input: AgentInput) -> AgentOutput:
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            timeout=self._settings.ai_timeout,
        )
        user_content = _USER_TEMPLATE.format(
            input_json=agent_input.model_dump_json(indent=2)
        )
        response = await client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_tokens=256,
        )
        raw = (response.choices[0].message.content or "").strip()
        return _parse_and_log(agent_input.symbol, raw)


def _parse_and_log(symbol: str, raw: str) -> AgentOutput:
    log.debug("AI raw response for %s: %s", symbol, raw)
    parsed = json.loads(raw)
    output = AgentOutput.model_validate(parsed)
    log.info(
        "AI decision | symbol=%s | decision=%s | confidence=%.2f | reason=%s",
        symbol,
        output.decision.value,
        output.confidence,
        output.reason,
    )
    return output


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _skip(reason: str) -> AgentOutput:
    return AgentOutput(decision=AgentDecision.SKIP, confidence=0.0, reason=reason)
