"""Profile questions: asked only when the answer changes the products, skipped when already known, answered by
button or in the customer's own words (English + Arabic), and every answer really changes the suggestion."""
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider
from tests.test_off_topic import chat


def ids(r):
    rt = next(c["routine"] for c in r["cards"] if c["type"] == "routine")
    return [x["id"] for x in rt["steps"]], [x["id"] for x in rt["addons"]]


def test_skin_type_is_asked_for_a_short_message_and_oily_adds_the_pore_toner():
    s, _, out = chat("how can I be fair", "btn:concerns_done")
    assert s.stage == "ask_q:skin_type"
    assert [q["action"] for q in out[-1]["quick_replies"]][:4] == ["q:skin_type:dry", "q:skin_type:oily",
                                                                   "q:skin_type:combination", "q:skin_type:normal"]
    s, _, out = chat("how can I be fair", "btn:concerns_done", "my skin is quite oily")
    assert "pores" in s.concerns and s.answers["skin_type"] == "oily"


def test_skin_type_is_not_asked_when_already_known():
    s, _, _ = chat("my skin is dry", "btn:concerns_done")
    assert "skin_type" not in s.answers and s.stage != "ask_q:skin_type"


def test_sensitivity_only_when_an_exfoliant_is_possible_and_it_removes_it():
    s, _, out = chat("my skin looks dull", "btn:concerns_done", "btn:q:skin_type:normal")
    assert s.stage == "ask_q:sensitivity"  # the dull-skin routine has an exfoliant, so it matters
    s, _, out = chat("my skin looks dull", "btn:concerns_done", "btn:q:skin_type:normal", "yes it's sensitive", "btn:budget:none")
    steps, addons = ids(out[-1])
    assert "nn1-exfoliant" not in steps + addons and "exfoliates" in out[-1]["text"]
    s, _, _ = chat("I have dark spots", "btn:concerns_done", "btn:q:skin_type:normal")
    assert s.stage != "ask_q:sensitivity"  # no exfoliant for dark spots: not asked


def test_essentials_keeps_one_product_per_concern():
    flow = ["btn:area:skin", "btn:concern:fine_lines", "btn:concern:dryness", "btn:concern:dark_spots", "btn:concerns_done"]
    s, _, out = chat(*flow)
    assert s.stage == "ask_q:routine_size"
    _, _, full = chat(*flow, "btn:q:routine_size:complete", "btn:budget:none")
    _, _, ess = chat(*flow, "btn:q:routine_size:essentials", "btn:budget:none")
    f_steps, _ = ids(full[-1])
    e_steps, e_addons = ids(ess[-1])
    assert len(e_steps) < len(f_steps) and set(f_steps) <= set(e_steps + e_addons)


def test_hair_questions_change_the_wash():
    s, _, out = chat("my hair is frizzy", "btn:concerns_done")
    assert s.stage == "ask_q:hair_type"
    s, _, out = chat("my hair is frizzy", "btn:concerns_done", "it's curly", "flaky scalp", "no, natural", "btn:budget:none")
    steps, addons = ids(out[-1])
    assert steps[0] == "cystiphane-dandruff" and "luxliss-curl-shine" in steps + addons
    assert s.answers == {"hair_type": "curly", "scalp": "dandruff", "colour": "no"}


def test_arabic_typed_answers():
    s, _, out = chat("شعري منفوش", "btn:concerns_done", "مموج", "سليمة", "نعم مصبوغ", "btn:budget:none")
    assert s.answers == {"hair_type": "wavy", "scalp": "fine", "colour": "yes"} and "colour_treated" in s.concerns
    s, _, out = chat("شعري منفوش", "btn:concerns_done", "مموج", "سليمة", "لا")
    assert s.answers["colour"] == "no"


def test_not_sure_or_unclear_answers_never_loop():
    s, _, out = chat("my skin feels dull", "btn:concerns_done", "not sure")
    assert s.answers["skin_type"] == "unsure"
    s, _, out = chat("my skin feels dull", "btn:concerns_done", "hmm", "asdf")
    assert s.answers["skin_type"] == "skip" and s.stage != "ask_q:skin_type"


def test_at_most_three_questions_and_detailed_messages_skip_them():
    s, _, out = chat("my hair is frizzy and dry")
    assert not s.answers and any(c["type"] == "routine" for c in out[0]["cards"])  # detailed: straight to it
    s, _, _ = chat("I want vitamins for my hair", "btn:concerns_done", "btn:q:supp_safety:none")
    s2, _, _ = chat("my skin feels dull", "btn:concerns_done", "btn:q:skin_type:normal", "btn:q:sensitivity:none")
    assert len([v for v in s2.answers.values() if not v.startswith("auto:")]) <= 3


def test_supplements_always_get_the_safety_check():
    s, _, out = chat("I want vitamins for my hair", "btn:concerns_done")
    assert s.stage == "ask_q:supp_safety" and not out[-1]["cards"]
    _, _, out = chat("I want vitamins for my hair", "btn:concerns_done", "btn:q:supp_safety:yes")
    assert out[-1]["kind"] == "handoff"
    _, _, out = chat("I want vitamins for my hair", "btn:concerns_done", "no, none of these")
    assert any(c["type"] == "routine" for c in out[-1]["cards"])


def test_off_topic_during_a_question_comes_back_to_it():
    s, _, out = chat("my hair is frizzy", "btn:concerns_done", "tell me a joke")
    assert out[-1]["kind"] == "off_topic" and s.stage == "ask_q:hair_type"
    assert any(q["action"] == "q:hair_type:curly" for q in out[-1]["quick_replies"])


def test_nothing_else_moves_on_in_both_languages():
    for done in ("nothing else", "that's all", "no", "بس كذا", "لا", "خلاص"):
        s, _, _ = chat("my hair is frizzy", done)
        assert s.concerns_done and s.stage == "ask_q:hair_type", done
    s, _, out = chat("I need something for better sleep", "that's all")
    assert s.stage == "ask_q:supp_safety" and not out[-1]["cards"]


def test_typed_sensitivity_answers():
    for msg, want in (("yes it gets red easily", "sensitive"), ("no", "none"), ("not really", "none"), ("نعم حساسة", "sensitive")):
        s, _, _ = chat("my skin looks dull", "btn:concerns_done", "btn:q:skin_type:normal", msg)
        assert s.sensitivity == want, msg
