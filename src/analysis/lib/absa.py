"""Lightweight, transparent heuristic ABSA (aspect-based sentiment analysis).

Explicitly a keyword-taxonomy + VADER lexicon approach, not a contextual
transformer model. Known weakness (documented, not hidden): naive keyword
matching can misread contrastive sentences like "the food wasn't bad but the
service was terrible" -- both clauses get matched, but clause-level
sentiment attribution is approximate, not clause-parsed. Good enough for a
directional, inspectable prototype; not a claim of state-of-the-art NLP.
"""
from __future__ import annotations

import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

ASPECT_KEYWORDS = {
    "FOOD": [
        "food", "meal", "burger", "pizza", "sandwich", "fries", "taste", "tasty", "flavor", "flavour",
        "chicken", "delicious", "bland", "fresh", "stale", "undercooked", "overcooked", "cold food",
        "portion", "menu item", "ingredient", "topping", "sauce", "crust", "dough",
    ],
    "SERVICE": [
        "service", "server", "customer service", "rude", "friendly", "helpful", "attentive", "greeted",
        "greet", "polite", "impolite", "manager", "ignored", "attitude", "unfriendly", "welcoming",
    ],
    "STAFF": [
        "staff", "employee", "worker", "team member", "cashier", "cook", "barista", "crew",
        "staff member", "personnel",
    ],
    "CLEANLINESS": [
        "clean", "dirty", "filthy", "sanitary", "unsanitary", "spotless", "messy", "hygiene", "hygienic",
        "grimy", "sticky floor", "gross", "smell", "smelled", "roach", "bug", "trash", "restroom",
        "bathroom",
    ],
    "WAITING_TIME": [
        "wait", "waited", "waiting", "slow", "fast", "quick", "quickly", "line", "queue", "took forever",
        "long time", "minutes", "hour", "delay", "delayed", "prompt", "speedy", "backed up", "drive thru",
        "drive-thru",
    ],
    "ORDER_ACCURACY": [
        "wrong order", "incorrect order", "missing item", "missing items", "forgot my",
        "gave me the wrong", "order was mixed up", "order mixed up", "incorrect item", "didn't receive",
        "missed my order", "wrong item", "never got my", "not what i ordered", "missing from my order",
        "order was wrong", "got the wrong", "wrong food item", "forgot to include", "order was incomplete",
    ],
    "VALUE": [
        "price", "priced", "expensive", "cheap", "overpriced", "worth", "value", "cost", "affordable",
        "deal", "pricey", "rip off", "ripoff", "bang for your buck",
    ],
}

# Domain lexicon nudges: phrases generic VADER often mishandles in a QSR
# context. Small, targeted, and disclosed -- not a black box.
DOMAIN_LEXICON_UPDATES = {
    "took forever": -2.5,
    "rip off": -2.5,
    "ripoff": -2.5,
    "roach": -3.0,
    "filthy": -2.8,
    "unsanitary": -2.8,
    "backed up": -1.5,
    "spotless": 2.5,
    "bang for your buck": 2.0,
    "worth it": 2.0,
    "wrong order": -2.2,
    "missing item": -2.0,
    "missing items": -2.0,
    "order was mixed up": -2.2,
    "never got my": -1.8,
    "order was incomplete": -1.8,
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_analyzer = None


def get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        a = SentimentIntensityAnalyzer()
        a.lexicon.update(DOMAIN_LEXICON_UPDATES)
        _analyzer = a
    return _analyzer


def split_sentences(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def match_aspects(sentence_lower: str) -> set[str]:
    hits = set()
    for aspect, keywords in ASPECT_KEYWORDS.items():
        for kw in keywords:
            if kw in sentence_lower:
                hits.add(aspect)
                break
    return hits


def score_review(review_text: str) -> list[dict]:
    """Returns a list of {ASPECT, SENTIMENT, N_SENTENCES} — at most one row
    per aspect per review (aggregated across matched sentences), so a long
    review repeating one topic can't overweight the business score."""
    analyzer = get_analyzer()
    sentences = split_sentences(review_text)
    if not sentences:
        return []

    aspect_scores: dict[str, list[float]] = {}
    for sent in sentences:
        sent_lower = sent.lower()
        aspects = match_aspects(sent_lower)
        if not aspects:
            continue
        compound = analyzer.polarity_scores(sent)["compound"]
        for a in aspects:
            aspect_scores.setdefault(a, []).append(compound)

    return [
        {"ASPECT": a, "SENTIMENT": sum(v) / len(v), "N_SENTENCES": len(v)}
        for a, v in aspect_scores.items()
    ]
