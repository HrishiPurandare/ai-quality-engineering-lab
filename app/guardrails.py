"""Guardrails: cheap, deterministic filters around the model.

Three layers, each answering one question:

1. Input guard   - is this message an obvious attack?           -> block it before retrieval
                 - does it contain a card number?               -> redact it before the model sees it
2. Context guard - does a retrieved passage contain instructions -> drop those lines (indirect injection)
                   aimed at the assistant?
3. Output guard  - is the reply unsafe to show?                  -> replace it with a safe message

They are a seatbelt, not a cure: regexes catch known phrasings, not every phrasing. That is why
the red team is re-run against attacks written AFTER these rules (redteam/attacks_holdout.jsonl).

Note: the output guard deliberately does NOT look for the red-team canary codes (PWNED-...).
Those strings only exist in our tests; a guard that searched for them would make the red-team
score look better without making the bot any safer.
"""

import re
from dataclasses import dataclass

from app.prompts import NO_ANSWER, SYSTEM_PROMPT

BLOCKED_REPLY = (
    "I can only help with questions about NovaBank products and policies. "
    "For anything else, please contact NovaBank on 800-NOVA."
)
UNSAFE_OUTPUT_REPLY = (
    "Sorry, I can't share that. I can help with questions about NovaBank products and policies. "
    "Never share your card number, PIN, CVV or one-time password with anyone, including this chat."
)

# --- 1. Input guard -------------------------------------------------------------------------
INJECTION_PATTERNS = {
    "override_instructions": r"\b(ignore|disregard|forget|override)\b[^.?!\n]{0,30}"
    r"\b(instructions?|rules?|prompts?|guidelines?)\b",
    "persona_switch": r"\b(developer|debug|god|jailbreak|admin)\s+mode\b|\byou are (now )?dan\b|\bno rules\b",
    "prompt_extraction": r"\b(system prompt|your (instructions|rules|prompt)|"
    r"the text above|everything above)\b",
    "persistent_instruction": r"\bfrom now on\b|\b(end|start|begin) (every|each|all|your) "
    r"(answers?|repl(y|ies)|responses?|messages?)\b",
    "encoded_payload": r"\b(decode|base64|rot13)\b",
}
_INJECTION = {name: re.compile(p, re.IGNORECASE) for name, p in INJECTION_PATTERNS.items()}

CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
CVV_MENTION = re.compile(r"\b(cvv|cvc|security code)\b\D{0,10}\d{3,4}\b", re.IGNORECASE)


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, d in enumerate(int(c) for c in reversed(digits)):
        total += d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
    return total % 10 == 0


def redact_card_numbers(text: str) -> str:
    def _mask(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        return "[REDACTED CARD]" if 13 <= len(digits) <= 19 and luhn_valid(digits) else match.group()

    text = CARD_CANDIDATE.sub(_mask, text)
    return CVV_MENTION.sub("[REDACTED CVV]", text)


@dataclass(frozen=True)
class InputVerdict:
    text: str  # the question to use (card numbers redacted)
    blocked_by: str | None = None
    redacted: bool = False


def check_input(question: str) -> InputVerdict:
    for name, pattern in _INJECTION.items():
        if pattern.search(question):
            return InputVerdict(text=question, blocked_by=f"input:{name}")
    cleaned = redact_card_numbers(question)
    return InputVerdict(text=cleaned, redacted=cleaned != question)


# --- 2. Context guard -----------------------------------------------------------------------
# Policy documents describe the bank to customers. They never address "the assistant", never
# tell it what to say first, and never claim to override rules. Lines that do are dropped.
CONTEXT_INSTRUCTION = re.compile(
    # Not just the word "assistant": the real security policy describes the virtual assistant.
    r"\binstructions? (for|to) the (assistant|chatbot|ai|model)\b|"
    r"\b(assistant|chatbot|ai|model) (must|should|shall)\b|"
    r"\b(ignore|override|overrides|disregard)\b[^.\n]{0,40}\b(instructions?|rules?)\b|"
    r"\bstart your (answer|reply|response)\b|"
    r"\b(reply|respond) with (their|your) (card|otp|pin|password)",
    re.IGNORECASE,
)


def sanitise_passage(text: str) -> tuple[str, bool]:
    """Remove instruction-like paragraphs from a retrieved passage. Returns (text, changed)."""
    paragraphs = re.split(r"\n\s*\n", text)
    kept = [p for p in paragraphs if not CONTEXT_INSTRUCTION.search(p)]
    return "\n\n".join(kept), len(kept) != len(paragraphs)


# --- 3. Output guard ------------------------------------------------------------------------
SECRET_REQUEST = re.compile(
    r"\b(share|send|provide|give|tell|reply with|confirm|type|enter)\b[^.?!\n]{0,40}?"
    r"\b(card number|pin|otp|one-time password|one time password|cvv|password)\b",
    re.IGNORECASE,
)
NEGATION = re.compile(r"\b(never|not|don't|do not|won't|will not|cannot|can't)\b", re.IGNORECASE)
CODE = re.compile(r"```|^\s*(import|def|for|while|print\()", re.MULTILINE)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


_PROMPT_NGRAMS = _ngrams(_words(SYSTEM_PROMPT.replace(NO_ANSWER, "")), 8)


def check_output(reply: str) -> str | None:
    """Name of the rule the reply breaks, or None if it is safe to show."""
    for match in CARD_CANDIDATE.finditer(reply):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            return "output:card_number"
    for sentence in re.split(r"(?<=[.!?\n])\s+", reply):
        if SECRET_REQUEST.search(sentence) and not NEGATION.search(sentence):
            return "output:secret_request"
    if _ngrams(_words(reply), 8) & _PROMPT_NGRAMS:
        return "output:system_prompt_leak"
    if CODE.search(reply):
        return "output:code"
    return None
