"""The Mouldproof agent: photos -> facts -> hazard call -> legal clock -> landlord record -> letters.

Models: Nemotron VL inspects the photos, Nano structures the tenant's story,
Ultra (reasoning) makes the hazard call, Super checks evidence and writes.
Dates, deadlines and scope are computed in code (app/law.py).
"""
import json
import re
from datetime import date

from . import law, llm, research


def event(step: str, status: str, **payload) -> dict:
    return {"step": step, "status": status, **payload}


GENERIC = {"homes", "housing", "group", "association", "council", "borough", "city", "district", "the", "and",
           "of", "trust", "limited", "ltd", "london", "metropolitan", "royal"}


def plain(text: str) -> str:
    """Letters are sent as plain text; drop any markdown emphasis the model adds."""
    return re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M).strip()


def about(text: str, name: str) -> bool:
    words = [w for w in name.lower().replace(",", " ").split() if w not in GENERIC and len(w) > 2]
    return bool(words) and any(w in text.lower() for w in words)


def run(photos: list[tuple[str, str]], story: str, today: date | None = None):
    today = today or date.today()
    llm.USAGE.clear()

    # 1. Inspect the photos (Nemotron VL)
    findings = {"photos": []}
    if photos:
        yield event("inspect", "running", tier="vision")
        findings = llm.vision_json(photos, f"""You are helping a tenant in England document damp and mould for their landlord.
There are {len(photos)} photo(s), in order. Describe only what is visible; say "unclear" rather than guess.
Return JSON:
{{"photos": [{{"n": 1, "location": "e.g. bedroom window reveal, ceiling corner",
              "what_is_visible": "one factual sentence",
              "extent": "small (under a dinner plate) | moderate (up to ~1 m²) | extensive (over ~1 m²) | unclear",
              "signs": ["black spot mould", "condensation", "frost or ice", "peeling paint", "water staining", "tide marks", "salts", "damaged plaster"],
              "likely_cause": "condensation | penetrating damp | rising damp | leak | unclear",
              "cause_reason": "short reason based on what is visible"}}],
 "overall": "two sentences summarising the damp and mould across all photos"}}""",
                                   step="Inspect photos")
        yield event("inspect", "done", tier="vision", result=findings)

    # 2. Structure the tenant's story (Nano)
    yield event("facts", "running", tier="nano")
    facts = llm.chat_json("nano", [
        {"role": "system", "content": "You extract facts from a tenant's description of a housing problem. Reply with JSON only. Use null when something isn't stated; never guess dates."},
        {"role": "user", "content": f"""Today is {today.isoformat()}.
Tenant's description:
\"\"\"{story}\"\"\"

Return JSON:
{{"landlord_name": "name or null",
  "landlord_type": "council | housing_association | private | unknown",
  "tenure": "tenant | owner | leaseholder | shared_ownership | licence | unknown",
  "first_reported": "YYYY-MM-DD the landlord was first told, or null (resolve phrases like 'six weeks ago' against today)",
  "how_reported": "phone / email / repairs portal / in person / null",
  "investigated_on": "YYYY-MM-DD the landlord inspected, or null",
  "landlord_actions": ["what the landlord has done or said"],
  "household": ["who lives there, with ages if given"],
  "vulnerabilities": ["e.g. baby, child with asthma, pregnancy, older person, respiratory or immune condition"],
  "symptoms": ["health effects mentioned"],
  "rooms": ["rooms affected"]}}"""},
    ], step="Structure your story", max_tokens=900)
    yield event("facts", "done", tier="nano", result=facts)

    # 3. Hazard call (Ultra, reasoning on)
    yield event("assess", "running", tier="ultra")
    assessment = llm.chat_json("ultra", [
        {"role": "system", "content": "You assess damp and mould in English social housing against Awaab's Law. "
                                      "Awaab's Law covers damp and mould that presents a significant risk of harm to the health or safety of the occupier, "
                                      "and emergency hazards that present an imminent and significant risk of harm. Risk depends on extent, location "
                                      "(e.g. bedrooms) and the vulnerability of occupiers (babies, children, older people, people with respiratory or "
                                      "immune conditions, pregnancy). Most damp and mould affecting vulnerable people is 'significant'. Use 'emergency' only "
                                      "when harm is imminent, e.g. someone currently in respiratory crisis, mould alongside a live leak onto electrics, or a "
                                      "ceiling at risk of collapse. Safety advice must be practical and safe: never suggest bleach or that the tenant "
                                      "removes large areas of mould themselves. Be careful and honest. Reply with JSON only."},
        {"role": "user", "content": f"""Photo findings: {json.dumps(findings)}
Tenant facts: {json.dumps(facts)}

Return JSON:
{{"classification": "emergency | significant | not_significant | unclear",
  "confidence": "high | medium | low",
  "headline": "one plain-English sentence for the tenant",
  "reasons": ["3-4 short reasons tied to the photos and household"],
  "safety_now": ["2-3 practical things to do today to reduce harm, not blaming the tenant"],
  "evidence_gaps": ["2-3 things to photograph or record to strengthen the case"]}}"""},
    ], step="Assess the hazard", max_tokens=8000, temperature=0.2, think=True)
    if assessment.get("classification") not in {"emergency", "significant", "not_significant", "unclear"}:
        assessment["classification"] = "unclear"
    yield event("assess", "done", tier="ultra", result=assessment)

    # 4. Legal clock (code)
    yield event("clock", "running")
    sc = law.scope(facts.get("landlord_type"), facts.get("tenure"))
    reported = law.parse_date(facts.get("first_reported"))
    investigated = law.parse_date(facts.get("investigated_on"))
    clock = {"scope": sc, "guidance_url": law.GUIDANCE_URL, "today": today.isoformat(),
             "reported": reported.isoformat() if reported else None, "items": []}
    if reported and reported > today:
        reported = None
    if sc["covered"] is not False and reported and assessment["classification"] in {"emergency", "significant"}:
        start = max(reported, law.IN_FORCE)
        clock["items"] = law.deadlines(start, assessment["classification"], investigated, today)
        clock["working_days_since_report"] = law.working_days_between(start, today)
    clock["any_overdue"] = any(i["status"] in {"overdue", "late"} for i in clock["items"])
    yield event("clock", "done", result=clock)

    # 5. Landlord track record (Tavily) + 6. evidence check (Super, verified in code)
    landlord = facts.get("landlord_name")
    record = {"landlord": landlord, "findings": []}
    if landlord:
        yield event("record", "running", tier="tavily")
        raw = research.landlord_record(landlord)
        yield event("record", "done", tier="tavily", result={k: len(v) for k, v in raw.items()})

        yield event("verify", "running", tier="super")
        results = [r for rs in raw.values() for r in rs]
        extracted = llm.chat_json("super", [
            {"role": "system", "content": "You summarise a social landlord's track record on damp and mould from search results. Only use the results given. Reply with JSON only."},
            {"role": "user", "content": f"""Landlord: {landlord}
Search results: {json.dumps(results)[:20000]}

Return up to 4 findings that are clearly about THIS landlord (not a different landlord with a similar name):
{{"findings": [{{"kind": "ombudsman | regulator | news",
                "summary": "one sentence, e.g. 'Ombudsman found severe maladministration over damp and mould in 2025'",
                "quote": "short phrase copied verbatim from the result supporting the summary",
                "url": "the result's url"}}]}}"""},
        ], step="Check landlord record", max_tokens=1500)
        by_url = {r["url"]: r for r in results}
        for f in extracted.get("findings", [])[:4]:
            src = by_url.get(f.get("url"))
            text = f"{src['title']} {src['content']}" if src else ""
            quote = (f.get("quote") or "").strip().lower()
            f["verified"] = bool(src) and bool(quote) and quote in text.lower() and about(text, landlord)
            if f["verified"]:
                f["source_title"] = src["title"]
                record["findings"].append(f)
        yield event("verify", "done", tier="super", result=record)

    # 7. Letters (Super)
    yield event("letters", "running", tier="super")
    deadline_lines = "\n".join(f"- {i['label']}: due {i['due']} ({i['rule']}) - {i['status'].upper()}" for i in clock["items"])
    photo_lines = "\n".join(f"- Photo {p.get('n')}: {p.get('location')}: {p.get('what_is_visible')} Extent: {p.get('extent')}."
                            for p in findings.get("photos", []))
    common = f"""Facts: {json.dumps(facts)}
Photo evidence:
{photo_lines or '- (no photos supplied)'}
Hazard assessment: {assessment.get('classification')} - {assessment.get('headline')}
Scope: {sc['why']}
Deadlines computed from the date reported ({clock['reported']}):
{deadline_lines or '- not computed'}
Use placeholders [Your name], [Address], [Tenancy reference], [Date]. Plain text, no markdown. Never invent facts or dates."""
    letter = llm.chat("super", [
        {"role": "system", "content": "You write firm, polite, factual letters for social-housing tenants in England."},
        {"role": "user", "content": f"""Write a formal letter to {landlord or 'the landlord'} titled "Damp and mould hazard - request for action under Awaab's Law".
State the hazard, the photo evidence (as attachments), the household's vulnerabilities, the legal timeframes from the Hazards in Social Housing (Prescribed Requirements) (England) Regulations 2025 and which are overdue, and ask for: an investigation date, the written summary, the make-safe work, and alternative accommodation if it cannot be made safe in time. Ask for a reply within 5 working days. Under 330 words.
{common}"""},
    ], step="Draft landlord letter", max_tokens=1500, temperature=0.3)
    complaint = ""
    if clock["any_overdue"]:
        complaint = llm.chat("super", [
            {"role": "system", "content": "You write clear complaints for social-housing tenants in England."},
            {"role": "user", "content": f"""Write a formal Stage 1 complaint to {landlord or 'the landlord'} under its complaints policy about the missed Awaab's Law deadlines below, asking for the remedy (repairs, the written summary, compensation for distress and inconvenience) and stating that if unresolved the tenant will refer the matter to the Housing Ombudsman Service. Under 250 words.
{common}"""},
        ], step="Draft complaint", max_tokens=1200, temperature=0.3)
    letter, complaint = plain(letter), plain(complaint)
    yield event("letters", "done", tier="super", result={"letter": letter, "complaint": complaint})

    yield event("complete", "done", result={"usage": llm.USAGE, "models": llm.MODELS})
