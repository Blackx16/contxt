#!/usr/bin/env python3
"""Emit copy-paste-ready Kimi prompts (each batch fully substituted).

Browser workflow: open finetune/KIMI_BATCHES.md, copy one block, paste into Kimi,
save the reply. No hand-editing of {{BATCH_SPEC}}/{{N}}.

    python finetune/make_batches.py          # v1: 12 balanced batches (~1,200 rows)
    python finetune/make_batches.py --all     # all 40 batches (~4,000 rows)
"""
from __future__ import annotations
import argparse
import pathlib

# The master prompt body (mirror of finetune/KIMI_PROMPT.md), with two literal
# tokens we string-replace per batch. NOT str.format() — the JSON examples contain
# literal { } braces.
POLICY = r'''You are generating a supervised dataset to fine-tune a tiny on-device privacy
classifier for "Contxt". It reads ONE short personal-data item (an email line, a
calendar event, or a note) and decides PRIVATE vs SHARED, a sensitivity score,
categories, and a one-line reason.

Output {{N}} realistic, diverse, correctly-labeled examples for this batch:

>> BATCH: {{BATCH_SPEC}}

OUTPUT FORMAT — STRICT
- Output ONLY JSONL: exactly {{N}} lines, one JSON object per line.
- No markdown, no code fences, no commentary, no blank lines, no trailing commas.
- Every line is valid JSON with double quotes, in EXACTLY this key order:
{"text": "...", "tier": "PRIVATE", "sensitivity": 0.0, "categories": ["..."], "reason": "...", "source": "gmail", "region": "IN", "lang": "en", "difficulty": "medium", "hard_negative": false}

FIELD DICTIONARY (fill EVERY field on EVERY line)
- text: the item as it would really appear. <= 300 chars. Realistic but FICTIONAL
  (invented names, plausible-but-fake amounts, fake phone/card numbers — never a real
  person or real card). Vary wording/entities heavily; no near-duplicates.
- tier: "PRIVATE" or "SHARED" (uppercase). Policy below.
- sensitivity: float 0.0-1.0, two decimals. PRIVATE >= 0.50; SHARED <= 0.35;
  reserve 0.35-0.50 for genuinely borderline items only.
- categories: 1-3 tags from the CLOSED VOCAB below. No other strings. No "kw:" prefixes.
- reason: <= 12 words, states the signal (no step-by-step reasoning).
- source: "gmail" | "calendar" | "notion" (match phrasing to the source).
- region: "IN" (Rs/lakh/crore/GST/Indian names/+91) or "GLOBAL". Follow the BATCH.
- lang: "en" or "hinglish" (Roman-script code-mix, e.g. "kal client ko invoice bhejni
  hai"). NEVER Devanagari. Follow the BATCH.
- difficulty: "easy" | "medium" | "hard". Follow the BATCH ("mixed" = spread across all).
- hard_negative: true if it's a trap (SHARED that looks sensitive, or PRIVATE that looks
  mundane), else false.

TIER POLICY (must be internally consistent)
PRIVATE = crown jewels that must never leave the device:
  - ANY money amount/magnitude (Rs, ₹, $, €, "8.5 lakh", "2 crore", "$1.2M", "millions").
  - Finance words even without a number: salary, revenue, profit, turnover, payroll,
    invoice, valuation, funding, acquisition, net worth, bank balance.
  - Card numbers, bank account numbers ("A/c 1234..."), phone numbers.
  - Health: diagnosis, prescription, medical reports, clinic/therapy/test results.
  - Family & home matters, children/school specifics, relationship issues.
  - Client-confidential or deal details (pricing, contracts, at-risk accounts, churn).
  - Credentials: passwords, OTPs, API keys, tokens, secrets.
  - Anything a person would not want a third-party AI to read.
SHARED = safe for an AI assistant: general work, public info, routine scheduling,
  non-sensitive logistics, published content, learning resources.
HARD RULE: if text contains any money amount/magnitude, a finance word above, a
card/account/phone number, or a health term, the row is PRIVATE — no exceptions.
Labeling such a thing SHARED is the worst possible error. When unsure, choose PRIVATE.

SENSITIVITY BANDS
- 0.90-1.00 hard money amounts, card/account numbers, credentials, explicit diagnosis
- 0.70-0.89 salary/loan/EMI, client-confidential/deal, family/personal health, legal
- 0.50-0.69 implied / borderline sensitive -> still PRIVATE
- 0.25-0.49 mildly personal but shareable, or truly ambiguous -> SHARED
- 0.00-0.24 clearly public / work / routine scheduling

CLOSED CATEGORY VOCAB (use only these)
money, finance, card, account, phone, health, family, clients, credentials, legal,
work, scheduling, travel, personal, location, misc

DIVERSITY FOR THIS BATCH
- Follow the BATCH's tier bias, region, language, source, difficulty.
- Vary entities/amounts/dates/phrasings heavily; imagine many different people.
- If the BATCH asks for hard negatives, make >= 60% of lines hard_negative: true and
  genuinely tricky. Do not reuse the example sentences below.

GOLD EXAMPLES (imitate the SHAPE, not the content)
{"text": "Your ICICI home-loan EMI of Rs 62,400 is due on the 7th; auto-debit is on.", "tier": "PRIVATE", "sensitivity": 0.95, "categories": ["money", "finance"], "reason": "loan EMI amount", "source": "gmail", "region": "IN", "lang": "en", "difficulty": "easy", "hard_negative": false}
{"text": "kal Acme wale client ko renewal ka pricing bhejna hai, warna deal slip ho jayegi", "tier": "PRIVATE", "sensitivity": 0.8, "categories": ["clients", "finance"], "reason": "confidential client pricing", "source": "notion", "region": "IN", "lang": "hinglish", "difficulty": "medium", "hard_negative": false}
{"text": "Standup moved to 10:30, same Meet link, agenda is the sprint burndown.", "tier": "SHARED", "sensitivity": 0.1, "categories": ["scheduling", "work"], "reason": "routine meeting logistics", "source": "calendar", "region": "GLOBAL", "lang": "en", "difficulty": "easy", "hard_negative": false}
{"text": "Free public webinar on salary negotiation — share the signup link with anyone.", "tier": "SHARED", "sensitivity": 0.15, "categories": ["work"], "reason": "public content despite money word", "source": "gmail", "region": "GLOBAL", "lang": "en", "difficulty": "hard", "hard_negative": true}
{"text": "Call mom before her follow-up on Tuesday, she's anxious about the results.", "tier": "PRIVATE", "sensitivity": 0.82, "categories": ["family", "health"], "reason": "family medical follow-up", "source": "calendar", "region": "GLOBAL", "lang": "en", "difficulty": "hard", "hard_negative": true}

Now output the {{N}} JSONL lines for this batch. Output only the JSONL.'''

# (id, N, spec)
V1 = [
    ("b01", 100, "IN, gmail, mostly PRIVATE, finance/loans/EMI/GST/invoices, en, mixed difficulty"),
    ("b03", 100, "IN, notion, mostly PRIVATE, client deals/pricing/at-risk accounts, en, medium-hard"),
    ("b05", 100, "IN, gmail, mostly PRIVATE, health reports/diagnosis/pharmacy, en, easy-medium"),
    ("b06", 100, "IN, notion, mostly SHARED, project notes/architecture/learning, en, easy-medium"),
    ("b07", 100, "IN, calendar, mostly SHARED, standups/reviews/public events, en, easy"),
    ("b08", 100, "IN, gmail+notion, HARD NEGATIVES: shared-looking-sensitive (public salary webinars, published case studies, blog drafts), en, hard"),
    ("b09", 100, "IN, gmail+calendar, HARD PRIVATES: mundane-looking-private (implied family/health/deal, no trigger word), en, hard"),
    ("b10", 100, "IN, gmail, mostly PRIVATE, finance/loans/EMI, hinglish, mixed"),
    ("b12", 100, "IN, calendar, mixed, family+health vs work scheduling, hinglish, mixed"),
    ("b19", 100, "IN, gmail+notion, mixed 50/50 across all categories, en, mixed"),
    ("b21", 100, "GLOBAL, gmail, mostly PRIVATE, finance/salary/invoices ($/€/£), en, mixed"),
    ("b25", 100, "GLOBAL, notion, mostly SHARED, project/eng notes/learning resources, en, easy-medium"),
]
# The remaining 28 (see KIMI_PROMPT.md matrix) — appended when --all is passed.
REST = [
    ("b02", 100, "IN, gmail, mostly PRIVATE, salary/payroll/bank-balance/UPI receipts, en, easy-medium"),
    ("b04", 100, "IN, calendar, mixed, family/school/health appointments vs work meetings, en, mixed"),
    ("b11", 100, "IN, notion, mostly PRIVATE, client/deal/vendor, hinglish, medium"),
    ("b13", 100, "IN, gmail, mostly SHARED, newsletters/receipts-for-public-stuff/logistics, hinglish, easy-medium"),
    ("b14", 100, "IN, notion, mixed, personal journal vs shareable work notes, hinglish, hard"),
    ("b15", 100, "IN, gmail, mostly PRIVATE, credentials/OTP/passwords/API keys, en, easy"),
    ("b16", 100, "IN, notion, mixed, legal/contracts/disputes vs public policy docs, en, medium-hard"),
    ("b17", 100, "IN, calendar, mixed, travel tied to money/family vs plain work trips, en, medium"),
    ("b18", 100, "IN, gmail, HARD NEGATIVES: promo/marketing emails that quote prices but are public, en+hinglish, hard"),
    ("b20", 100, "IN, calendar+notion, mixed 50/50 across all categories, hinglish, mixed"),
    ("b22", 100, "GLOBAL, notion, mostly PRIVATE, client deals/pricing/churn, en, medium-hard"),
    ("b23", 100, "GLOBAL, gmail, mostly PRIVATE, health/insurance/medical bills, en, easy-medium"),
    ("b24", 100, "GLOBAL, calendar, mixed, family/kids/health vs work meetings, en, mixed"),
    ("b26", 100, "GLOBAL, calendar, mostly SHARED, standups/design syncs/public conferences, en, easy"),
    ("b27", 100, "GLOBAL, gmail, mostly SHARED, newsletters/product updates/logistics, en, easy-medium"),
    ("b28", 100, "GLOBAL, gmail+notion, HARD NEGATIVES: shared-looking-sensitive (public earnings blog, transparency reports), en, hard"),
    ("b29", 100, "GLOBAL, gmail+calendar, HARD PRIVATES: implied sensitivity, no trigger word, en, hard"),
    ("b30", 100, "GLOBAL, gmail, mostly PRIVATE, credentials/2FA/secrets, en, easy"),
    ("b31", 100, "GLOBAL, notion, mixed, legal/NDA/contracts vs public T&Cs, en, medium-hard"),
    ("b32", 100, "GLOBAL, calendar, mixed, travel tied to money/personal vs plain work trips, en, medium"),
    ("b33", 100, "GLOBAL, gmail+notion, mixed 50/50 across all categories, en, mixed"),
    ("b34", 100, "IN, gmail, mostly PRIVATE, family finances/property/gold/insurance, en, medium"),
    ("b35", 100, "IN, notion, mixed, founder notes (fundraise/cap-table PRIVATE vs roadmap SHARED), en, hard"),
    ("b36", 100, "GLOBAL, notion, mixed, founder notes (fundraise/burn PRIVATE vs roadmap SHARED), en, hard"),
    ("b37", 100, "IN, calendar, mostly PRIVATE, personal (doctor/lawyer/bank/parent-teacher), en, medium"),
    ("b38", 100, "GLOBAL, gmail, mixed 50/50, phone numbers + contact-sharing edge cases, en, medium"),
    ("b39", 100, "IN+GLOBAL, notion, mixed, location/home-address/whereabouts sensitivity, en, medium-hard"),
    ("b40", 100, "IN+GLOBAL, gmail+calendar+notion, mixed 50/50 wildcard — maximize variety, en+hinglish, mixed"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="emit all 40 batches (default: 12 v1)")
    ap.add_argument("--out", default="finetune/KIMI_BATCHES.md")
    args = ap.parse_args()

    batches = V1 + REST if args.all else V1
    total = sum(n for _, n, _ in batches)
    out = [
        f"# Ready-to-paste Kimi batches ({len(batches)} batches ≈ {total} rows)\n",
        "For each batch: **copy the whole block**, paste into Kimi, then save the reply as\n"
        "`finetune/dataset/raw/<id>.jsonl` (e.g. `kimi_b01.jsonl`). Order doesn't matter.\n"
        "Generated by `make_batches.py` — regenerate with `--all` for the full 40.\n",
    ]
    for bid, n, spec in batches:
        prompt = POLICY.replace("{{N}}", str(n)).replace("{{BATCH_SPEC}}", spec)
        out.append(f"\n---\n\n## {bid} → save as `finetune/dataset/raw/kimi_{bid}.jsonl`\n")
        out.append("```text\n" + prompt + "\n```\n")

    pathlib.Path(args.out).write_text("".join(out), encoding="utf-8")
    print(f"wrote {len(batches)} batches (~{total} rows) -> {args.out}")


if __name__ == "__main__":
    main()
