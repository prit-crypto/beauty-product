"""Consultation profile questions: asked only when the answer changes which products are suggested.

Each question:
  - applies to one area and is asked only if `needed(session, catalog)` says its answer would change the routine
    (for example skin sensitivity is asked only when the routine would include the exfoliant or the peel);
  - is skipped when the customer already said the answer (in any message);
  - has options that map to real catalogue data (concern tags, a setting, or a hand-off), plus "Not sure";
  - can be answered with a button or in the customer's own words (English or Arabic).

At most MAX_QUESTIONS are asked per consultation, and a detailed first message skips them (except the supplement
safety check, which is always asked before a supplement is suggested).
"""
from dataclasses import dataclass, field
from typing import Callable

import re

from app.engine.text import AR_CHARS, find_terms, normalize

MAX_QUESTIONS = 3

UNSURE_KW = ["not sure", "don't know", "dont know", "no idea", "unsure", "skip", "whatever", "any", "مو متاكده", "مش متاكده",
             "لا اعرف", "ما اعرف", "مش عارفه", "مدري", "تخطي"]
YES_KW = ["yes", "yeah", "yep", "i am", "i'm", "sure", "نعم", "اي", "ايوه", "ايه", "اكيد"]
NO_KW = ["no", "nope", "none", "neither", "not", "nothing", "لا", "ابدا", "ولا شي", "ولا واحد", "مو", "مش"]


@dataclass
class Option:
    value: str
    kw: list[str] = field(default_factory=list)  # words that mean this option (normalised matching, EN + AR)
    add_concern: str | None = None


@dataclass
class Question:
    key: str
    area: str
    options: list[Option]
    needed: Callable  # (session, catalog) -> bool
    always: bool = False  # asked even after a detailed first message (safety)


def _preview_steps(s, cat):
    """The products the routine would have right now (used to decide if a question matters)."""
    from app.engine.recommender import build
    r = build(cat, s.area, s.concerns, None, exclude=s.excluded)
    return r.steps + r.addons


def _has_exfoliant(s, cat) -> bool:
    return any(st.product["step"] in ("exfoliant", "peel") for st in _preview_steps(s, cat))


def _has_overlap(s, cat) -> bool:
    from app.engine.recommender import build
    steps = build(cat, s.area, s.concerns, None, exclude=s.excluded).steps
    if len(steps) < 3:
        return False
    return any(set(x.covers) <= {c for y in steps if y is not x for c in y.covers} for x in steps if x.covers)


QUESTIONS: list[Question] = [
    # ---- skin
    Question("skin_type", "skin", [
        Option("dry", ["dry", "جافه", "جاف", "ناشفه"], "dryness"),
        Option("oily", ["oily", "greasy", "shiny", "دهنيه", "دهني"], "pores"),
        Option("combination", ["combination", "combo", "mixed", "t-zone", "مختلطه", "مختلط"], "pores"),
        Option("normal", ["normal", "balanced", "عاديه", "طبيعيه"]),
        Option("unsure", UNSURE_KW),
    ], needed=lambda s, cat: not ({"dryness", "pores"} & set(s.concerns))),
    Question("sensitivity", "skin", [
        Option("none", ["not sensitive", "no", "normal", "not really", "ليست حساسه", "مو حساسه", "مش حساسه", "لا"]),
        Option("sensitive", ["sensitive", "irritat", "redness", "gets red", "goes red", "red easily", "reactive", "yes", "yeah", "burn", "sting", "حساسه", "تتهيج", "احمرار", "نعم"]),
    ], needed=lambda s, cat: s.sensitivity is None and _has_exfoliant(s, cat)),
    Question("routine_size", "skin", [
        Option("essentials", ["essential", "simple", "minimal", "basic", "few", "just the", "short", "اساسي", "بسيط", "قليل"]),
        Option("complete", ["complete", "full", "everything", "all", "كامل", "كل"]),
    ], needed=lambda s, cat: _has_overlap(s, cat)),
    # ---- hair
    Question("hair_type", "hair", [
        Option("straight", ["straight", "sleek", "ناعم", "سايح", "مفرود"]),
        Option("wavy", ["wavy", "waves", "مموج", "متموج"]),
        Option("curly", ["curly", "curls", "coily", "كيرلي", "مجعد", "كيرلي"], "curly"),
        Option("unsure", UNSURE_KW),
    ], needed=lambda s, cat: "curly" not in s.concerns),
    Question("scalp", "hair", [
        Option("dandruff", ["dandruff", "flaky", "flakes", "flake", "itchy", "قشره", "حكه"], "dandruff"),
        Option("hair_fall", ["fall", "falling", "shedding", "losing", "تساقط", "يتساقط", "يطيح"], "hair_fall"),
        Option("fine", ["fine", "healthy", "normal", "ok", "no", "none", "سليمه", "عاديه", "تمام", "لا"]),
    ], needed=lambda s, cat: not ({"dandruff", "hair_fall", "thinning"} & set(s.concerns))),
    Question("colour", "hair", [
        Option("yes", ["yes", "colour", "color", "dyed", "bleach", "highlight", "balayage", "henna", "نعم", "مصبوغ", "صبغه", "ميش", "هايلايت"],
               "colour_treated"),
        Option("no", ["no", "natural", "never", "not", "لا", "طبيعي"]),
    ], needed=lambda s, cat: bool({"dry_damaged", "frizz"} & set(s.concerns)) and "colour_treated" not in s.concerns),
    # ---- supplements: a safety check before any supplement is suggested
    Question("supp_safety", "supplement", [
        Option("none", ["no", "none", "neither", "not", "nothing", "لا", "ولا شي", "ولا واحد"]),
        Option("yes", ["yes", "pregnant", "breastfeed", "medication", "medicine", "under 18", "نعم", "حامل", "مرضع", "دواء", "ادويه"]),
    ], needed=lambda s, cat: True, always=True),
]
BY_KEY = {q.key: q for q in QUESTIONS}


DONE_KW = ["nothing else", "that's all", "thats all", "that's it", "thats it", "no more", "only that", "only this", "just that",
           "just this", "nope", "no", "nothing", "done", "بس", "بس كذا", "هذا كل شيء", "هذا كل شي", "لا", "فقط", "خلاص", "ولا شي", "كذا بس"]


def done_words(text: str) -> bool:
    """'Nothing else' at the "anything else?" step."""
    return bool(_hits(text, DONE_KW))


def next_question(s, cat) -> Question | None:
    asked = [k for k, v in s.answers.items() if not v.startswith("auto:")]
    for q in QUESTIONS:
        if q.area != s.area or q.key in s.answers:
            continue
        if s.fast_path and not q.always:
            continue
        if len(asked) >= MAX_QUESTIONS and not q.always:
            continue
        if q.needed(s, cat):
            return q
    return None


NEGATION = re.compile(r"(?<![a-z])(no|not|never|nope|none|don'?t|isn'?t|haven'?t)(?![a-z])")
AR_NEGATION = {"لا", "مو", "مش", "ما", "ليس", "ليست", "غير", "ابدا"}


def _hits(text: str, words: list[str]) -> list[str]:
    """Like find_terms, but very short Arabic words ("لا", "مو") must be a whole word, not part of "لازم" or "موجود"."""
    tokens = set(re.findall(r"[؀-ۿ]+", normalize(text)))
    out = []
    for w in words:
        wn = normalize(w)
        if AR_CHARS.search(wn) and len(wn) <= 3 and " " not in wn:
            if wn in tokens:
                out.append(w)
        elif find_terms(text, [w]):
            out.append(w)
    return out


def match_option(q: Question, text: str) -> Option | None:
    """The option a typed answer means, or None. Longer, more specific words win ("not sensitive" over "sensitive"),
    and in yes/no questions a negation means no ("not coloured", "لا")."""
    values = {o.value for o in q.options}
    n = normalize(text)
    negated = bool(NEGATION.search(n)) or bool(AR_NEGATION & set(re.findall(r"[؀-ۿ]+", n)))
    if negated and {"yes", "no"} <= values:
        return next(o for o in q.options if o.value == "no")
    best, best_len = None, 0
    for o in q.options:
        for w in _hits(text, o.kw):
            if len(w) > best_len:
                best, best_len = o, len(w)
    return best


def apply(s, q: Question, value: str) -> None:
    """Record the answer and its effect on the consultation."""
    s.answers[q.key] = value
    opt = next((o for o in q.options if o.value == value), None)
    if opt and opt.add_concern and opt.add_concern not in s.concerns:
        s.concerns.append(opt.add_concern)
    if q.key == "sensitivity":
        s.sensitivity = "sensitive" if value == "sensitive" else "none"
    if q.key == "routine_size":
        s.essentials = value == "essentials"


def note_known(s) -> None:
    """Answers the customer already gave (e.g. "my curly hair", "I'm not sensitive"): those questions are skipped."""
    if s.sensitivity and "sensitivity" not in s.answers and s.area == "skin":
        s.answers["sensitivity"] = "auto:" + s.sensitivity
