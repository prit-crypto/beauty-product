"""Deterministic routine builder. The AI never chooses products or prices; this module does.

Every product is chosen ONLY because one of its verified concern tags (catalog.json, reviewed against the real store
description) matches a concern the customer stated. Each step records which concerns it is for. Concerns that no
product addresses are reported as `uncovered`, so the assistant can say plainly that we don't have a product for them.
Rules are our draft of Dr. Shaymaa's guidance and live in one place so she can adjust them.
"""
from dataclasses import dataclass, field

from app.engine.catalog import Catalog

# A routine is built from roles. Each role offers candidate products; a candidate is used only when its tags overlap
# the customer's concerns. priority: lower = more important (higher numbers are dropped first to fit a budget).
SKIN_STANDARD_ROLES = [
    ("day", ["nn1-day-cream"], "AM", 1),
    ("night", ["nn1-night-cream"], "PM", 1.5),
    ("treat", ["nn1-brightening-cream"], "PM", 2),
    ("eye", ["nn1-eye-cream"], "AM & PM", 3),
    ("exfoliate", ["nn1-exfoliant"], "Once or twice a week", 3.5),
    ("toner", ["nn1-toner"], "AM", 4),
]
SKIN_PREMIUM_ROLES = [
    ("serum", ["cana-hydro-serum", "cana-brightening-serum", "cana-oxygen-brightening", "cana-instant-lifting"], "AM & PM", 1),
    ("moisturizer", ["cana-moisturizer"], "AM & PM", 1.5),
    ("eye", ["cana-eye-serum"], "AM & PM", 3),
    ("mask", ["cana-collagen-mask", "cana-magnetic-mask", "cana-deep-peel"], "Once a week", 3.5),
    ("toner", ["cana-toner"], "AM", 4),
]
SKIN_PREMIUM_POOL = [pid for _, ids, _, _ in SKIN_PREMIUM_ROLES for pid in ids]
# medicated washes come first: a dandruff or hair-fall shampoo is the wash while that problem is active
HAIR_WASHES = ["cystiphane-dandruff", "cystiphane-shampoo", "luxliss-colour-protect", "luxliss-curl-shine",
               "luxliss-repair-restore", "luxliss-nourish-gloss", "luxliss-volume-boost"]
HAIR_ROLES = [
    ("mask", ["luxliss-argan-mask"], "After shampoo", 2),
    ("scalp", ["cystiphane-lotion", "hair-elixir"], "Daily, on the scalp", 2.5),
    ("finish", ["luxliss-argan-serum"], "After washing", 4),
]
# a role only answers the concerns it is meant for (a scalp elixir is not the answer to "damaged lengths")
ROLE_SCOPE = {"scalp": {"hair_fall", "thinning"}, "eye": {"dark_circles", "fine_lines", "sagging", "dryness"}}
SMOOTHING = "protein-nano-gold-botox"  # straightens: never for customers who said they have curly hair
SUPPLEMENTS = ["ivybears-women-hair", "ivybears-hair", "ivybears-vibrant-skin", "ivybears-boost-immune", "ivybears-restful-sleep"]


@dataclass
class Step:
    product: dict
    slot: str
    priority: float
    covers: list[str] = field(default_factory=list)  # the customer's concerns this product is for
    note: str = ""  # e.g. "alternative" or "alternate_wash"

    @property
    def concern(self) -> str:
        return self.covers[0] if self.covers else ""


@dataclass
class Routine:
    area: str
    tier: str  # standard | premium | full
    steps: list[Step] = field(default_factory=list)
    dropped: list[Step] = field(default_factory=list)
    addons: list[Step] = field(default_factory=list)
    budget: int | None = None
    over_budget_minimum: bool = False
    tips: list[str] = field(default_factory=list)  # template keys
    caution: bool = False
    uncovered: list[str] = field(default_factory=list)  # concerns we have no product for

    @property
    def total(self) -> float:
        return sum(s.product["price_aed"] for s in self.steps)

    @property
    def full_total(self) -> float:
        return self.total + sum(s.product["price_aed"] for s in self.dropped)

    def to_dict(self) -> dict:
        def sd(s: Step) -> dict:
            p = s.product
            return {"id": p["id"], "name": p["name"], "line": p["line"], "price_aed": p["price_aed"], "slot": s.slot,
                    "summary": p["summary"], "summary_ar": p.get("summary_ar"), "how_to_use": p["how_to_use"],
                    "concern": s.concern, "covers": s.covers, "note": s.note, "caution": p["caution"],
                    "handoff": p["handoff"], "category": p["category"], "image": p.get("image")}
        return {"area": self.area, "tier": self.tier, "budget": self.budget, "total": self.total,
                "full_total": self.full_total, "steps": [sd(s) for s in self.steps],
                "dropped": [sd(s) for s in self.dropped], "addons": [sd(s) for s in self.addons],
                "tips": self.tips, "caution": self.caution, "over_budget_minimum": self.over_budget_minimum,
                "uncovered": self.uncovered}


def _covers(p: dict, concerns: list[str]) -> list[str]:
    return [c for c in concerns if c in p["concerns"]]


def _best(cat: Catalog, ids: list[str], concerns: list[str], exclude: set[str]) -> tuple[dict | None, list[str]]:
    """The candidate covering the most stated concerns (earlier in the list wins ties). None if none is relevant."""
    best, best_cov = None, []
    for pid in ids:
        if pid in exclude or pid not in cat.by_id:
            continue
        cov = _covers(cat.get(pid), concerns)
        if len(cov) > len(best_cov):
            best, best_cov = cat.get(pid), cov
    return best, best_cov


def _fill_roles(cat: Catalog, r: Routine, roles: list, concerns: list[str], exclude: set[str]) -> None:
    for role, ids, slot, pri in roles:
        scope = [c for c in concerns if c in ROLE_SCOPE.get(role, set(concerns))]
        p, cov = _best(cat, ids, scope, exclude | {s.product["id"] for s in r.steps})
        if p:
            r.steps.append(Step(p, slot, pri, cov))


def _fit_budget(r: Routine) -> None:
    """A stated budget is a limit: drop the least important products until the routine fits.

    If even the single most important product is above budget, keep the most affordable relevant one and flag it.
    Optional extras are only offered when they fit in what is left of the budget.
    """
    if not r.budget or not r.steps:
        return
    while r.total > r.budget and len(r.steps) > 1:
        # drop first what is redundant (its concerns are covered by another step), then by priority
        def redundant(s: Step) -> bool:
            others = {c for o in r.steps if o is not s for c in o.covers}
            return bool(s.covers) and set(s.covers) <= others
        worst = max(r.steps, key=lambda s: (redundant(s), s.priority, s.product["price_aed"]))
        r.steps.remove(worst)
        r.dropped.append(worst)
    if r.total > r.budget:
        candidates = r.steps + r.dropped
        fitting = [s for s in candidates if s.product["price_aed"] <= r.budget]
        keep = min(fitting, key=lambda s: (s.priority, s.product["price_aed"])) if fitting else \
            min(candidates, key=lambda s: s.product["price_aed"])
        r.dropped = [s for s in candidates if s is not keep]
        r.steps = [keep]
        r.over_budget_minimum = keep.product["price_aed"] > r.budget
    room = r.budget - r.total
    r.addons = [a for a in r.addons if a.product["price_aed"] <= room]


def build(cat: Catalog, area: str, concerns: list[str], budget: int | None, premium: bool = False,
          exclude: list[str] | None = None, fill: bool = False, essentials: bool = False) -> Routine:
    """exclude: products the customer took out (they stay out). fill: use the budget for every relevant extra."""
    concerns = list(dict.fromkeys(concerns))
    ex = set(exclude or [])
    if area == "skin":
        r = _skin(cat, concerns, budget, premium, ex)
    elif area == "hair":
        r = _hair(cat, concerns, budget, ex)
    else:
        r = _supplement(cat, concerns, ex)
    r.steps = [s for s in r.steps if s.product["id"] not in ex]
    r.addons = [s for s in r.addons if s.product["id"] not in ex]
    if fill:  # "my budget is higher, add more": every relevant extra that is not a supplement joins the routine
        r.tier = "full" if r.tier == "standard" else r.tier
        for a in list(r.addons):
            if not a.product["caution"]:
                r.steps.append(Step(a.product, a.slot, a.priority + 1, a.covers, a.note))
                r.addons.remove(a)
    if essentials:  # "just the essentials": one product per concern; overlapping ones become optional extras
        while True:
            red = [x for x in r.steps if x.covers and set(x.covers) <= {c for y in r.steps if y is not x for c in y.covers}]
            if not red:
                break
            worst = max(red, key=lambda x: (x.priority, x.product["price_aed"]))
            r.steps.remove(worst)
            r.addons.insert(0, worst)
    # truly uncovered = no product in the range for it (things only left out for budget don't count)
    covered = {c for s in r.steps + r.addons for c in s.covers}
    r.uncovered = [c for c in concerns if c not in covered]
    _fit_budget(r)
    return r


def _skin(cat: Catalog, concerns: list[str], budget: int | None, premium: bool, ex: set[str]) -> Routine:
    r = Routine(area="skin", tier="premium" if premium else "standard", budget=budget)
    _fill_roles(cat, r, SKIN_PREMIUM_ROLES if premium else SKIN_STANDARD_ROLES, concerns, ex)
    if premium and not r.steps:  # nothing in the luxury line fits these concerns: fall back to the everyday line
        r.tier = "standard"
        _fill_roles(cat, r, SKIN_STANDARD_ROLES, concerns, ex)
    if not premium:
        # concerns the everyday line doesn't cover, or a luxury upgrade: offered as clearly labelled extras
        covered = {c for s in r.steps for c in s.covers}
        missing = [c for c in concerns if c not in covered]
        alt, cov = _best(cat, SKIN_PREMIUM_POOL, missing or concerns, ex)
        if alt:
            r.addons.append(Step(alt, "Alternative" if missing else "Premium upgrade", 6, cov, "alternative" if missing else ""))
    if r.steps:
        r.tips.append("tip_cleanser_spf")
    return r


def _hair(cat: Catalog, concerns: list[str], budget: int | None, ex: set[str]) -> Routine:
    r = Routine(area="hair", tier="standard", budget=budget)
    cs = set(concerns)
    _fill_roles(cat, r, HAIR_ROLES, concerns, ex)
    wash, cov = None, []
    if "dandruff" in cs and "cystiphane-dandruff" not in ex:
        wash, cov = cat.get("cystiphane-dandruff"), ["dandruff"]
    elif "hair_fall" in cs and "cystiphane-shampoo" not in ex:
        wash, cov = cat.get("cystiphane-shampoo"), ["hair_fall"]
    else:
        # the wash goes to what the mask/serum/scalp products don't already cover (e.g. curls), then to the rest
        others = {c for s in r.steps for c in s.covers}
        open_concerns = [c for c in concerns if c not in others]
        wash, _ = _best(cat, HAIR_WASHES[2:], open_concerns, ex) if open_concerns else (None, [])
        if not wash:
            wash, _ = _best(cat, HAIR_WASHES[2:], concerns, ex)
        cov = _covers(wash, concerns) if wash else []
    if wash:
        r.steps.insert(0, Step(wash, "Every wash", 1, cov))
    covered = {c for s in r.steps for c in s.covers}
    # a second wash for what the medicated shampoo doesn't cover (e.g. curls), used on alternate days
    if wash and wash["id"].startswith("cystiphane"):
        other, ocov = _best(cat, HAIR_WASHES[2:], [c for c in concerns if c not in covered], ex)
        if other:
            r.addons.append(Step(other, "Alternate wash", 5, ocov, "alternate_wash"))
            covered |= set(ocov)
    if "frizz" in cs and "frizz" not in covered:
        p, c2 = _best(cat, ["luxliss-nourish-gloss"], ["frizz"], ex)
        if p and p["id"] not in {s.product["id"] for s in r.steps}:
            r.addons.append(Step(p, "Alternate wash", 5, c2, "alternate_wash"))
            covered |= set(c2)
    # salon smoothing (it straightens): only when asked for, never for customers who said they have curly hair
    if "straightening" in cs and "curly" not in cs and SMOOTHING not in ex:
        p = cat.get(SMOOTHING)
        r.addons.append(Step(p, "Salon-style treatment", 6, _covers(p, concerns)))
    if cs & {"thinning", "hair_fall"} and "ivybears-women-hair" not in ex:
        r.addons.append(Step(cat.get("ivybears-women-hair"), "Supplement", 6, []))
        r.caution = True
    return r


def _supplement(cat: Catalog, concerns: list[str], ex: set[str]) -> Routine:
    r = Routine(area="supplement", tier="standard", caution=True)
    for c in concerns:
        p, cov = _best(cat, SUPPLEMENTS, [c], ex | {s.product["id"] for s in r.steps})
        if p:
            r.steps.append(Step(p, "Daily", 1, cov))
    r.tips.append("tip_supplement")
    return r
