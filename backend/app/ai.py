"""Deterministic mock AI. Transparent rule-based outputs; no model/API calls."""
from __future__ import annotations
import re
from .data import CATEGORIES

CRITICAL = ['fire','burning','electrocution','electrocuted','collapsed','collapse','fatal','death',
            'life threatening','live wire','exposed wire','injured','violence','attack',
            'आग','मौत','जान को खतरा','गिर गया','टूटकर','घायल','करंट']
HIGH = ['danger','urgent','emergency','no water','three days','kids','children','unsafe','contaminated',
        'hospital','ambulance','threat','sewage','risk','dangerous','तुरंत','खतरा','बच्चे','परेशान','चोट']


def matches_term(text: str, term: str) -> bool:
    """Match complete Latin words/phrases, not substrings inside unrelated words."""
    term = term.casefold()
    if all(ord(c) < 128 for c in term):
        return re.search(r'(?<![a-z])' + re.escape(term) + r'(?![a-z])', text) is not None
    # Hindi forms have combining marks; substring search is more reliable than ASCII word boundaries.
    return term in text


def analyze(text: str, title: str = '', image_hint: str = '') -> dict:
    """Approximate classification/triage for demo. Never use as real emergency routing."""
    text = f'{title} {text} {image_hint}'.strip()
    low = text.casefold()
    scores = {}
    matches = {}
    for cat in CATEGORIES[:-1]:
        hits = [key for key in cat['keywords'] if matches_term(low, key)]
        scores[cat['name']] = sum(2 if ' ' in k else 1 for k in hits)
        matches[cat['name']] = hits
    best = max(scores, key=scores.get) if scores else 'Other'
    if scores.get(best, 0) == 0:
        best = 'Other'
    category = next(c for c in CATEGORIES if c['name'] == best)
    evidence = matches.get(best, [])
    critical_terms = [term for term in CRITICAL if matches_term(low, term)]
    high_terms = [term for term in HIGH if matches_term(low, term)]
    priority = 'critical' if critical_terms else ('high' if high_terms else ('medium' if best != 'Other' else 'low'))
    urgency_score = {'critical':96, 'high':79, 'medium':52, 'low':24}[priority]
    confidence = round(min(0.96, 0.51 + 0.105 * len(evidence) + 0.04 * (scores.get(best,0) > 2)), 2) if evidence else 0.36
    hours = category['sla_hours']
    estimate = max(6, round(hours * {'critical': 0.28,'high':0.65,'medium':1,'low':1.25}[priority]))
    devanagari = len(re.findall(r'[\u0900-\u097f]', text))
    language = 'Hindi' if devanagari > max(4, len(text) * .15) else 'English / Romanized'
    rationale = (f'Matched terms: {", ".join(evidence[:4])}. ' if evidence else 'No strong category terms detected. ') + (
        f'Priority increased because of: {", ".join((critical_terms or high_terms)[:3])}. ' if critical_terms or high_terms else
        'No immediate safety keywords identified. ') + 'This is a heuristic demo recommendation, not an official decision.'
    return {
        'category':best,'department':category['department'],'priority':priority,
        'urgency_score':urgency_score,'confidence':confidence,'estimated_hours':estimate,
        'rationale':rationale,'tags':evidence[:5], 'language':language,
        'requires_human_review': priority == 'critical' or confidence < 0.58,
        'safety_flags':critical_terms[:4], 'model_version':'mock-rules-v1',
    }


def mock_image_description(filename: str) -> str:
    """Make the limitation explicit; only uses filenames, NOT actual image pixels."""
    low = filename.lower().replace('_',' ').replace('-',' ')
    words = ['anganwadi','building','road','pothole','garbage','water','leak','electric','school','hospital']
    found = [w for w in words if w in low]
    if found:
        return f'Filename hint: {", ".join(found)}. Image contents have NOT been analyzed; add a written description.'
    return 'Photo received. Mock vision cannot inspect image pixels; please add a description.'
