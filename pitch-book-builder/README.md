# Pitch Book Auto-Builder — Prototype

> A junior banker spends a weekend building a first draft. This does it
> in about ninety seconds — not to replace the banker, but so they start
> Monday at the 80% mark.

A live-demo prototype for senior investment banking executives. Takes a
natural-language engagement brief, filters synthetic market data, runs
real valuation analyses, and asks Claude to draft a complete preliminary
M&A pitch book plus a one-page MD talking-points sheet.

## What the demo shows

- **Reasoning across structured and unstructured data.** The model reads
  a filtered comps table, a precedents table, a prose market environment
  note, and a brief written in plain English, and weaves them into a
  coherent narrative.
- **Honest numbers.** All figures are pre-computed deterministically in
  `valuation.py` and handed to the model as a factbook. The system prompt
  forbids invented numbers — executives can trust what lands on the page.
- **Tone control.** The brief can specify sell-side vs. buy-side,
  strategic vs. financial buyers, meeting context, and tone
  (conservative / balanced / aggressive). Watch the output change.
- **A second artifact for free.** The talking-points sheet is the
  sleeper hit — the MD's prep document for the meeting, generated in
  the same run.

## Run the demo

```bash
cd pitch-book-builder
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python pitch.py "Pitch NorthStar Analytics as a sell-side opportunity to \
strategic acquirers. Focus on SaaS data peers. Client is the CFO, first \
meeting, conservative tone."
```

Outputs land in `output/`:

- `pitch_book.md` — the full nine-section preliminary pitch book
- `talking_points.md` — a one-page MD brief for the meeting

### Dry-run (no API key needed)

To inspect the deterministic factbook the model will receive — useful
for verifying the math before a demo:

```bash
python pitch.py "any brief" --dry-run
```

## What to watch for in the live demo

1. **The football field section.** A real banker artifact, rendered in
   ASCII, with the DCF range clearly tighter than the multiples-based
   methods — exactly how a trained eye would expect it to behave.
2. **The peer selection commentary.** The model explains *why* it
   included the comps it did, referencing growth, scale, and margin.
3. **The talking-points sheet.** Ask the audience to read it alone. It
   reads like something a Managing Director would actually carry in.

## Files

```
pitch-book-builder/
├── data/
│   ├── comps.csv                 # 15 synthetic trading comparables
│   ├── precedents.csv            # 12 synthetic M&A transactions
│   ├── target_financials.json    # "NorthStar Analytics" — fictional target
│   └── market_context.md         # Prose market environment note
├── valuation.py                  # DCF, comps, precedents, sensitivity, football field
├── pitch.py                      # CLI entry point — factbook + Claude call
├── requirements.txt
└── README.md
```

## Disclaimer

All data in `data/` is synthetic and illustrative. Company names,
tickers, transaction details, and financial figures are fictional and
must not be used for any investment decision. This is a capability
demonstration only.
