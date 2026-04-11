#!/usr/bin/env python3
"""M&A pitch book auto-builder prototype.

Takes a natural-language engagement brief, filters synthetic market data,
runs valuation analyses, and asks Claude to draft a complete preliminary
pitch book and a one-page MD talking-points sheet.

All numerical figures in the generated output must trace back to the
reference data files or to valuation.py — the model is instructed to
refuse to invent figures.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from valuation import build_factbook, format_factbook_for_prompt

MODEL = "claude-sonnet-4-6"
DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = Path(__file__).parent / "output"


SYSTEM_PERSONA = """You are a senior investment banking analyst at a tier-one
global investment bank drafting client-facing deliverables for the Managing
Director on a live engagement. Your writing is measured, precise, and
understated — the tone of a formal bulge-bracket pitch book. You do not use
hype, exclamations, or marketing language. You never invent numerical facts.

CRITICAL CONSTRAINTS:
1. Every numerical figure in your output must come from the FACTBOOK in the
   user message or from the raw data files in context. If a number is not in
   those sources, omit it or mark it "to be confirmed". Never estimate,
   extrapolate, or fabricate.
2. Use formal English suitable for a CFO audience. No emoji, no casual
   language, no breathless adjectives.
3. Use banker phrasing: "the Transaction", "the Company", "the process",
   "strategic rationale", "consideration mix", "control premium".
4. Present figures with appropriate units ($m, x, %, bps) and sensible
   rounding (EV to nearest $10m, multiples to one decimal, percentages to
   one decimal).
"""


PITCH_BOOK_INSTRUCTIONS = """Draft a complete preliminary M&A pitch book for
the engagement described in the brief below. Use only the FACTBOOK and the
reference data in your system context. Do not invent figures.

Structure the output as a single markdown document with exactly these
numbered sections:

1. Executive Summary — the one-page view a Managing Director reads first
2. Situation Overview & Strategic Rationale
3. Company Snapshot — key metrics drawn from target_financials.json
4. Trading Comparables Analysis — include the filtered comps table and
   commentary on peer selection
5. Precedent Transactions Analysis — include the filtered precedents table
   and commentary
6. Preliminary Valuation Football Field — reproduce the ASCII chart from
   the factbook verbatim inside a fenced code block, then narrate the range
7. Potential Buyer Universe — 5 to 7 named archetypes (for example,
   "large-cap enterprise software consolidator") with one-sentence rationale
8. Key Risks & Mitigants — 4 to 6 risks, each with a mitigant
9. Proposed Next Steps & Process Timeline

Match the tone to the brief (conservative / balanced / aggressive); default
to conservative if unclear. Open each section with a short italicized
standfirst summarising the takeaway in one sentence.

BRIEF:
{brief}

{factbook}
"""


TALKING_POINTS_INSTRUCTIONS = """Produce a separate one-page talking-points
document for the Managing Director to carry into the client meeting described
in the brief. Crisp and scannable:

- Opening line (how the MD should frame the meeting)
- Three key messages to anchor the conversation
- Expected client questions with prepared answers
- The single most important number to quote, and its source in the factbook
- What to offer as a follow-up

Keep under 500 words. Formal English. No emoji. Use only FACTBOOK figures.

BRIEF:
{brief}

{factbook}
"""


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict, str]:
    comps = pd.read_csv(DATA_DIR / "comps.csv")
    precedents = pd.read_csv(DATA_DIR / "precedents.csv")
    with open(DATA_DIR / "target_financials.json") as f:
        target = json.load(f)
    market_context = (DATA_DIR / "market_context.md").read_text()
    return comps, precedents, target, market_context


def build_system_blocks(comps_csv: str, precedents_csv: str,
                        target_json: str, market_context: str) -> list[dict]:
    data_block = (
        "REFERENCE DATA (synthetic — for prototype demonstration only)\n\n"
        "== comps.csv ==\n"
        f"{comps_csv}\n\n"
        "== precedents.csv ==\n"
        f"{precedents_csv}\n\n"
        "== target_financials.json ==\n"
        f"{target_json}\n\n"
        "== market_context.md ==\n"
        f"{market_context}\n"
    )
    return [
        {"type": "text", "text": SYSTEM_PERSONA},
        {"type": "text", "text": data_block, "cache_control": {"type": "ephemeral"}},
    ]


def call_claude(client, system_blocks: list[dict], user_text: str,
                max_tokens: int = 8000) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user_text}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def main() -> None:
    parser = argparse.ArgumentParser(description="M&A pitch book auto-builder prototype")
    parser.add_argument("brief", help="Natural-language engagement brief")
    parser.add_argument("--wacc", type=float, default=0.10,
                        help="WACC used for DCF (default: 0.10)")
    parser.add_argument("--terminal-growth", type=float, default=0.03,
                        help="Terminal growth rate for DCF (default: 0.03)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute and print the factbook only; skip the Claude call")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    comps, precedents, target, market_context = load_data()

    factbook = build_factbook(
        target=target,
        comps=comps,
        precedents=precedents,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
    )
    factbook_text = format_factbook_for_prompt(factbook)

    if args.dry_run:
        print(factbook_text)
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.",
              file=sys.stderr)
        sys.exit(1)

    from anthropic import Anthropic  # imported lazily so --dry-run works without the SDK
    client = Anthropic()

    system_blocks = build_system_blocks(
        comps_csv=(DATA_DIR / "comps.csv").read_text(),
        precedents_csv=(DATA_DIR / "precedents.csv").read_text(),
        target_json=json.dumps(target, indent=2),
        market_context=market_context,
    )

    print("Drafting pitch book...", flush=True)
    pitch_book = call_claude(
        client, system_blocks,
        PITCH_BOOK_INSTRUCTIONS.format(brief=args.brief, factbook=factbook_text),
        max_tokens=8000,
    )
    (OUT_DIR / "pitch_book.md").write_text(pitch_book)

    print("Drafting talking points...", flush=True)
    talking_points = call_claude(
        client, system_blocks,
        TALKING_POINTS_INSTRUCTIONS.format(brief=args.brief, factbook=factbook_text),
        max_tokens=2000,
    )
    (OUT_DIR / "talking_points.md").write_text(talking_points)

    print(f"\nOutputs written to {OUT_DIR}/")
    print("  - pitch_book.md")
    print("  - talking_points.md")


if __name__ == "__main__":
    main()
