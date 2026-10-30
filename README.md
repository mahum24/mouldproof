# Mouldproof

**Mould in your home? Your landlord is now on a legal clock.**

In 2020, two-year-old Awaab Ishak died from prolonged exposure to mould in his family's social-housing flat in Rochdale, after his family's complaints went unanswered. **Awaab's Law** (the Hazards in Social Housing (Prescribed Requirements) (England) Regulations 2025) came into force on 27 October 2025. Social landlords in England must now investigate damp and mould that puts tenants' health at significant risk **within 10 working days**, make it safe **within 5 working days** of the investigation, and send the tenant a written summary within 3 working days. Emergency hazards must be dealt with **within 24 hours**.

Those deadlines only help if tenants know they exist and can show they were missed. Mouldproof turns a few photos and a description of what happened into a case:

1. **Inspects the photos.** Nemotron 3.5 Super VL describes each one: where the mould is, how far it has spread, the visible signs (black spot mould, condensation, frost, tide marks) and the likely cause.
2. **Pulls the facts from the tenant's story.** Nemotron 3 Nano extracts the landlord, the dates it was reported and inspected, who lives there and their vulnerabilities. Relative dates ("six weeks ago") are resolved against today, and nothing is guessed.
3. **Judges the hazard level.** Nemotron 3 Ultra, with reasoning on, classifies the case as emergency, significant, lower risk or unclear, weighing extent, location and vulnerable occupants. It also gives safe advice for today and lists what to photograph next.
4. **Runs the legal clock in code.** The law engine works out whether Awaab's Law covers the home (it does for council and housing-association tenants; private renters are pointed to environmental health) and computes every deadline in working days, skipping weekends and the official gov.uk bank holidays. No model ever does date arithmetic.
5. **Checks the landlord's record with Tavily.** It searches Housing Ombudsman decisions, Regulator of Social Housing judgements and recent news.
6. **Verifies every finding.** Nemotron 3 Super summarises the record with a verbatim quote and a URL; code then checks that the source exists, names this landlord and contains the quote. Unverified findings are dropped.
7. **Writes the letters.** Nemotron 3 Super drafts a formal Awaab's Law letter (hazard, photo evidence, vulnerabilities, deadlines and what is overdue) and, if any deadline has passed, a Stage 1 complaint that sets up escalation to the Housing Ombudsman.

## NVIDIA Nemotron on Nebius Token Factory

| Step | Model | Reasoning |
|---|---|---|
| Inspect photos | `nvidia/Nemotron-3.5-Super-VL` | off |
| Structure the story | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | off |
| Judge the hazard | `nvidia/Nemotron-3-Ultra-550b-a55b` | **on** |
| Check landlord record | `nvidia/nemotron-3-super-120b-a12b` | off |
| Draft letter and complaint | `nvidia/nemotron-3-super-120b-a12b` | off |

All calls go through the Token Factory OpenAI-compatible API. Reasoning is switched off (`chat_template_kwargs.enable_thinking=false`) everywhere except the one judgement call, so a full case takes about 20 seconds. The UI shows the model, latency, tokens and reasoning tokens for every step.

## Models propose, code decides

- Scope and deadlines come from `app/law.py`, which follows MHCLG's *Awaab's Law: guidance for social landlords – timeframes for repairs* (updated 27 Oct 2025).
- The hazard class must be one of four allowed values, and the deadlines that apply depend on it.
- Claims about the landlord must survive a quote check against their cited source.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NEBIUS_API_KEY and TAVILY_API_KEY
uvicorn app.main:app --port 8000
```

Docker: `docker build -t mouldproof . && docker run -p 8000:8000 --env-file .env mouldproof`

## Limits

Mouldproof is not legal advice. It helps tenants document a problem and assert their rights; the landlord's investigation decides the formal hazard rating. For advice, contact Shelter or Citizens Advice.

## Example photo credits (Wikimedia Commons)

- `window.jpg`: "Mold and Frost by Window" by Tony Webster, CC BY 2.0
- `wall.jpg`: "Mold on wall1" by שי אבידן, CC BY-SA 4.0
- `corner.jpg`: "Black mold in a building" by NordhornerII, CC BY-SA 4.0
- `ceiling.jpg`: "Black Indoor Mold" by Couch-scratching-cats, public domain

## License

MIT (code). Example photos keep their original licenses listed above.
