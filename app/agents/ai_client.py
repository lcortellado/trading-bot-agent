"""
Claude API client for structured trading decisions.

Responsibilities:
- Build a strict system prompt that forces JSON-only output.
- Call Anthropic's messages API asynchronously.
- Validate the response with Pydantic (AgentOutput).
- On ANY failure (network, timeout, bad JSON, API error, missing SDK):
  return a SKIP decision so the rest of the flow is never blocked.

API key comes exclusively from Settings (env var AI_API_KEY).
"""
import json

from app.agents.schemas import AgentDecision, AgentInput, AgentOutput
from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# ─── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a crypto trading signal synthesizer embedded in a paper-trading bot.
Your job: analyze multiple indicators and produce ONE consolidated decision.

Definitions:
  ENTER       — signals align with sufficient confidence; proceed with trade
  SKIP        — signals conflict, confidence too low, or risk/reward unfavorable
  REDUCE_SIZE — signals lean in one direction but conviction is weak; enter smaller

Hard rules:
  - You are NOT the final risk authority. A RiskManager enforces hard capital limits after you.
  - Prefer SKIP over ENTER when uncertain — preserving capital is paramount.
  - Your reason MUST explain the specific signals that drove your decision.

Respond with VALID JSON ONLY — no markdown, no extra text:
{"decision": "ENTER"|"SKIP"|"REDUCE_SIZE", "confidence": 0.0–1.0, "reason": "explanation"}"""

_USER_TEMPLATE = """\
Analyze the following signal bundle and decide:

{input_json}

Respond with JSON only."""


# ─── Client ───────────────────────────────────────────────────────────────────


class AIDecisionClient:
    """
    Wraps Anthropic Claude for trading decisions.

    Fallback contract: any failure → SKIP (never raises, never blocks orders).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = bool(settings.ai_api_key) and settings.ai_enabled
        if not self._enabled:
            reason = (
                "AI_ENABLED=false" if not settings.ai_enabled else "AI_API_KEY not set"
            )
            log.warning(
                "AI decisions disabled (%s) — all calls will return SKIP fallback", reason
            )

    async def decide(self, agent_input: AgentInput) -> AgentOutput:
        """Return an AgentOutput. Never raises — falls back to SKIP on any error."""
        if not self._enabled:
            return _skip("AI decision client not configured — set AI_API_KEY to enable")
        try:
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
        # Lazy import so a missing anthropic package doesn't break startup;
        # ImportError is caught by the except clause in decide().
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic(api_key=self._settings.ai_api_key)
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
        log.debug("AI raw response for %s: %s", agent_input.symbol, raw)

        parsed = json.loads(raw)
        output = AgentOutput.model_validate(parsed)
        log.info(
            "AI decision | symbol=%s | decision=%s | confidence=%.2f | reason=%s",
            agent_input.symbol,
            output.decision.value,
            output.confidence,
            output.reason,
        )
        return output


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _skip(reason: str) -> AgentOutput:
    return AgentOutput(decision=AgentDecision.SKIP, confidence=0.0, reason=reason)
