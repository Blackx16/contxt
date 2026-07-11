# Kimi master prompt — Crown-Jewels Gateway training data

This generates the labeled data for the fine-tuned tier-classifier. **Kimi emits
compact rows** (item + label + metadata); `finetune/validate.py` then checks them,
dedups, and expands them into the ready-to-train Gemma chat format. We do it this
way because emitting the full chat turn per row would repeat the ~250-token
instruction 4,000× and waste most of your Kimi budget on boilerplate.

## How to run it

1. Open the **MASTER PROMPT** block below. It's self-contained — Kimi needs nothing else.
2. For each row of the **Batch matrix** (bottom of this file), replace `{{BATCH_SPEC}}`
   and `{{N}}` in the prompt with that row's values, and run it. That's ~40 runs of
   ~100 rows = ~4,000 examples. (If Kimi truncates at 100, split a spec into 2×50.)
3. Save each run's output as `finetune/dataset/raw/kimi_<id>.jsonl` (e.g. `kimi_b07.jsonl`).
   **Paste nothing but the JSONL** — no fences, no commentary.
4. Also generate the free seed rows: `python finetune/generate_seed.py`.
5. Validate + build the split: `python finetune/validate.py --in finetune/dataset/raw`.
   Read `finetune/dataset/REPORT.md`; if it flags `rule_violation_dropped`, open those
   batches — that's the dangerous error (a secret labeled shareable).

---

## MASTER PROMPT (copy everything between the lines)

---
You are generating a supervised dataset to fine-tune a tiny on-device privacy
classifier for "Contxt". The classifier reads ONE short personal-data item (an
email line, a calendar event, or a note) and decides whether it is **PRIVATE** or
**SHARED**, plus a sensitivity score, categories, and a one-line reason.

Your job: output **{{N}}** realistic, diverse, correctly-labeled examples for this
batch specification:

> **BATCH:** {{BATCH_SPEC}}

### Output format — STRICT
- Output **only JSONL**: exactly {{N}} lines, one JSON object per line.
- No markdown, no code fences, no commentary, no blank lines, no trailing commas.
- Every line must be valid JSON with double-quoted keys/strings, in EXACTLY this shape
  and key order:

`{"text": "...", "tier": "PRIVATE", "sensitivity": 0.0, "categories": ["..."], "reason": "...", "source": "gmail", "region": "IN", "lang": "en", "difficulty": "medium", "hard_negative": false}`

### Field dictionary (fill EVERY field on EVERY line)
- **text** — the item itself, as it would really appear. ≤ 300 characters. Realistic but
  FICTIONAL: invented names, plausible-but-fake amounts, fake phone/card numbers. Never a
  real person or real card number. Vary wording, entities, and structure across lines — no
  two lines may be near-duplicates.
- **tier** — `"PRIVATE"` or `"SHARED"` (uppercase). Decision policy below.
- **sensitivity** — float 0.0–1.0, two decimals. Banding below. PRIVATE items sit ≥ 0.50;
  SHARED items sit ≤ 0.35. Reserve 0.35–0.50 for genuinely borderline items only.
- **categories** — array of 1–3 tags from the CLOSED VOCAB below. No other strings. No
  `kw:` prefixes. Choose the most specific applicable tags.
- **reason** — ≤ 12 words, states the *signal* that drove the decision. No step-by-step
  reasoning. e.g. "mentions a loan EMI amount", "public webinar, safe to share".
- **source** — `"gmail"`, `"calendar"`, or `"notion"`. Match the phrasing to the source
  (calendar = short event titles/times; gmail = sender/subject/body lines; notion = notes).
- **region** — `"IN"` (Indian context: Rs/₹, lakh/crore, GST, Indian names, +91) or
  `"GLOBAL"`. Follow the BATCH spec.
- **lang** — `"en"` or `"hinglish"` (Roman-script code-mixed Hindi+English, e.g. "kal
  client ko invoice bhejni hai"). NEVER Devanagari script. Follow the BATCH spec.
- **difficulty** — `"easy"` (obvious), `"medium"`, or `"hard"` (subtle / no trigger word /
  looks like the other tier). Follow the BATCH spec; when it says "mixed", spread across all three.
- **hard_negative** — `true` if this row is a trap (SHARED text that looks sensitive, or
  PRIVATE text that looks mundane), else `false`.

### Tier decision policy (this MUST be internally consistent)
PRIVATE = crown jewels that must never leave the device:
  - ANY money amount or magnitude (₹, Rs, $, €, "8.5 lakh", "2 crore", "$1.2M", "millions").
  - Finance words even without a number: salary, revenue, profit, turnover, payroll,
    invoice, valuation, funding, acquisition, net worth, bank balance.
  - Card numbers, bank account numbers ("A/c 1234…"), phone numbers.
  - Health: diagnosis, prescription, medical reports, clinic/therapy/test results.
  - Family & home matters, children/school specifics, relationship issues.
  - Client-confidential or deal details (pricing, contracts, at-risk accounts, churn).
  - Credentials: passwords, OTPs, API keys, tokens, secrets.
  - Anything a person would not want a third-party AI to read.
SHARED = safe for an AI assistant to use: general work, public info, routine scheduling,
  non-sensitive logistics, published content, learning resources.
**HARD RULE:** if `text` contains any money amount/magnitude, a finance word above, a
card/account number, a phone number, or a health term, the row is **PRIVATE** — no
exceptions. Getting this wrong (labeling such a thing SHARED) is the worst possible error.
**When genuinely unsure, choose PRIVATE.**

### Sensitivity bands
- 0.90–1.00 hard money amounts, card/account numbers, credentials, explicit diagnosis
- 0.70–0.89 salary/loan/EMI, client-confidential/deal, family or personal health, legal
- 0.50–0.69 implied / borderline sensitive → still PRIVATE
- 0.25–0.49 mildly personal but shareable, or truly ambiguous → SHARED
- 0.00–0.24 clearly public / work / routine scheduling

### CLOSED category vocab (use only these)
`money`, `finance`, `card`, `account`, `phone`, `health`, `family`, `clients`,
`credentials`, `legal`, `work`, `scheduling`, `travel`, `personal`, `location`, `misc`

### Diversity requirements for THIS batch
- Follow the BATCH spec's tier bias, region, language, source, and difficulty.
- Vary entities/amounts/dates/phrasings heavily; imagine many different people.
- If the BATCH asks for hard negatives, make ≥ 60% of the lines `hard_negative: true`
  and genuinely tricky (not obvious).
- Do not reuse the example sentences shown below.

### Gold examples (imitate the SHAPE, not the content)
{"text": "Your ICICI home-loan EMI of Rs 62,400 is due on the 7th; auto-debit is on.", "tier": "PRIVATE", "sensitivity": 0.95, "categories": ["money", "finance"], "reason": "loan EMI amount", "source": "gmail", "region": "IN", "lang": "en", "difficulty": "easy", "hard_negative": false}
{"text": "kal Acme wale client ko renewal ka pricing bhejna hai, warna deal slip ho jayegi", "tier": "PRIVATE", "sensitivity": 0.8, "categories": ["clients", "finance"], "reason": "confidential client pricing", "source": "notion", "region": "IN", "lang": "hinglish", "difficulty": "medium", "hard_negative": false}
{"text": "Standup moved to 10:30, same Meet link, agenda is the sprint burndown.", "tier": "SHARED", "sensitivity": 0.1, "categories": ["scheduling", "work"], "reason": "routine meeting logistics", "source": "calendar", "region": "GLOBAL", "lang": "en", "difficulty": "easy", "hard_negative": false}
{"text": "Free public webinar on salary negotiation — share the signup link with anyone.", "tier": "SHARED", "sensitivity": 0.15, "categories": ["work"], "reason": "public content despite money word", "source": "gmail", "region": "GLOBAL", "lang": "en", "difficulty": "hard", "hard_negative": true}
{"text": "Call mom before her follow-up on Tuesday, she's anxious about the results.", "tier": "PRIVATE", "sensitivity": 0.82, "categories": ["family", "health"], "reason": "family medical follow-up", "source": "calendar", "region": "GLOBAL", "lang": "en", "difficulty": "hard", "hard_negative": true}

Now output the {{N}} JSONL lines for this batch. Output only the JSONL.
---

---

## Batch matrix (≈4,000 rows)

Run the master prompt once per row; substitute `{{BATCH_SPEC}}` (the "spec" cell) and
`{{N}}`. Save as `finetune/dataset/raw/kimi_<id>.jsonl`.

| id | N | spec ({{BATCH_SPEC}}) |
|----|---|-----------------------|
| b01 | 100 | IN, gmail, mostly PRIVATE, finance/loans/EMI/GST/invoices, en, mixed difficulty |
| b02 | 100 | IN, gmail, mostly PRIVATE, salary/payroll/bank-balance/UPI receipts, en, easy-medium |
| b03 | 100 | IN, notion, mostly PRIVATE, client deals/pricing/at-risk accounts, en, medium-hard |
| b04 | 100 | IN, calendar, mixed, family/school/health appointments vs work meetings, en, mixed |
| b05 | 100 | IN, gmail, mostly PRIVATE, health reports/diagnosis/pharmacy, en, easy-medium |
| b06 | 100 | IN, notion, mostly SHARED, project notes/architecture/learning, en, easy-medium |
| b07 | 100 | IN, calendar, mostly SHARED, standups/reviews/public events, en, easy |
| b08 | 100 | IN, gmail+notion, HARD NEGATIVES: shared-looking-sensitive (public salary webinars, published case studies, blog drafts), en, hard |
| b09 | 100 | IN, gmail+calendar, HARD PRIVATES: mundane-looking-private (implied family/health/deal, no trigger word), en, hard |
| b10 | 100 | IN, gmail, mostly PRIVATE, finance/loans/EMI, hinglish, mixed |
| b11 | 100 | IN, notion, mostly PRIVATE, client/deal/vendor, hinglish, medium |
| b12 | 100 | IN, calendar, mixed, family+health vs work scheduling, hinglish, mixed |
| b13 | 100 | IN, gmail, mostly SHARED, newsletters/receipts-for-public-stuff/logistics, hinglish, easy-medium |
| b14 | 100 | IN, notion, mixed, personal journal vs shareable work notes, hinglish, hard |
| b15 | 100 | IN, gmail, mostly PRIVATE, credentials/OTP/passwords/API keys, en, easy |
| b16 | 100 | IN, notion, mixed, legal/contracts/disputes vs public policy docs, en, medium-hard |
| b17 | 100 | IN, calendar, mixed, travel tied to money/family vs plain work trips, en, medium |
| b18 | 100 | IN, gmail, HARD NEGATIVES: promo/marketing emails that quote prices but are public, en+hinglish, hard |
| b19 | 100 | IN, gmail+notion, mixed 50/50 across all categories, en, mixed |
| b20 | 100 | IN, calendar+notion, mixed 50/50 across all categories, hinglish, mixed |
| b21 | 100 | GLOBAL, gmail, mostly PRIVATE, finance/salary/invoices ($/€/£), en, mixed |
| b22 | 100 | GLOBAL, notion, mostly PRIVATE, client deals/pricing/churn, en, medium-hard |
| b23 | 100 | GLOBAL, gmail, mostly PRIVATE, health/insurance/medical bills, en, easy-medium |
| b24 | 100 | GLOBAL, calendar, mixed, family/kids/health vs work meetings, en, mixed |
| b25 | 100 | GLOBAL, notion, mostly SHARED, project/eng notes/learning resources, en, easy-medium |
| b26 | 100 | GLOBAL, calendar, mostly SHARED, standups/design syncs/public conferences, en, easy |
| b27 | 100 | GLOBAL, gmail, mostly SHARED, newsletters/product updates/logistics, en, easy-medium |
| b28 | 100 | GLOBAL, gmail+notion, HARD NEGATIVES: shared-looking-sensitive (public earnings blog, transparency reports), en, hard |
| b29 | 100 | GLOBAL, gmail+calendar, HARD PRIVATES: implied sensitivity, no trigger word, en, hard |
| b30 | 100 | GLOBAL, gmail, mostly PRIVATE, credentials/2FA/secrets, en, easy |
| b31 | 100 | GLOBAL, notion, mixed, legal/NDA/contracts vs public T&Cs, en, medium-hard |
| b32 | 100 | GLOBAL, calendar, mixed, travel tied to money/personal vs plain work trips, en, medium |
| b33 | 100 | GLOBAL, gmail+notion, mixed 50/50 across all categories, en, mixed |
| b34 | 100 | IN, gmail, mostly PRIVATE, family finances/property/gold/insurance, en, medium |
| b35 | 100 | IN, notion, mixed, founder notes (fundraise/cap-table PRIVATE vs roadmap SHARED), en, hard |
| b36 | 100 | GLOBAL, notion, mixed, founder notes (fundraise/burn PRIVATE vs roadmap SHARED), en, hard |
| b37 | 100 | IN, calendar, mostly PRIVATE, personal (doctor/lawyer/bank/parent-teacher), en, medium |
| b38 | 100 | GLOBAL, gmail, mixed 50/50, phone numbers + contact-sharing edge cases, en, medium |
| b39 | 100 | IN+GLOBAL, notion, mixed, location/home-address/whereabouts sensitivity, en, medium-hard |
| b40 | 100 | IN+GLOBAL, gmail+calendar+notion, mixed 50/50 wildcard — maximize variety, en+hinglish, mixed |

**Targets after validation:** ~48% PRIVATE / ~52% SHARED; ~60% IN / ~40% GLOBAL; ~20%
Hinglish overall; every category represented; ≥ 500 hard rows (`difficulty:"hard"`); ≥ 300
`hard_negative:true`. `validate.py` prints the actual balance so you can top up thin slices.
