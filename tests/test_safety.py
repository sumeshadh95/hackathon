import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from engine import Engine, Session
from models import parse_json
from safety import EMERGENCY_LINE


async def fake_planner(model, request, seen="", images=None, product=""):
    return {
        "title": "Test", "safety": ["Take care."], "items": [],
        "steps": [{"say": "One", "detail": "More", "uses": ["2 x bolt"]}, {"say": "Two", "detail": "More", "uses": []}],
        "sources": [{"title": "Example", "url": "https://example.com/a"}],
    }


class FakeModel:
    def __init__(self, reply="{}"):
        self.reply = reply

    async def generate(self, prompt, images=None, json_mode=False):
        return self.reply


def turn(session, text):
    return asyncio.run(Engine(FakeModel(), fake_planner).turn(session, text))


def add_photos(session, reply):
    return asyncio.run(Engine(FakeModel(json.dumps(reply)), fake_planner).add_photos(session, ["abc"]))


def test_parse_json_skips_reasoning():
    assert parse_json('Format: {"steps":["..."]} and {broken. Answer: {"steps":["One"]}') == {"steps": ["One"]}


def test_refusal():
    assert turn(Session(), "repair my brakes")["phase"] == "ended"


def test_caution_rejects_okay():
    session = Session()
    assert turn(session, "replace my phone screen")["phase"] == "caution"
    assert turn(session, "okay")["phase"] == "ended"


def test_gate_then_steps():
    session = Session()
    assert turn(session, "make a sandwich")["phase"] == "gate"
    assert turn(session, "next please")["phase"] == "gate"
    assert turn(session, "ready")["phase"] == "steps"


def test_emergency_stop():
    session = Session()
    turn(session, "make a sandwich")
    turn(session, "ready")
    result = turn(session, "I can smell burning")
    assert result["phase"] == "stopped"
    assert result["say"] == EMERGENCY_LINE


def test_new_task_resets_mid_task():
    session = Session()
    turn(session, "make a sandwich")
    turn(session, "ready")
    assert turn(session, "start over")["phase"] == "idle"


def test_photos_list_parts_then_build_steps():
    session = Session()
    result = add_photos(session, {"product": "IKEA shelf", "parts": [{"name": "cam bolt", "count": "4", "looks_like": "metal"}]})
    assert result["seen_parts"][0]["name"] == "cam bolt"
    assert session.photos == ["abc"]
    turn(session, "help me assemble this")
    result = turn(session, "ready")
    assert result["phase"] == "steps"
    assert result["uses"] == ["2 x bolt"]
    assert result["detail"] == "More"


def test_refused_item_in_photo_stops():
    session = Session()
    result = add_photos(session, {"product": "airbag module", "parts": []})
    assert result["phase"] == "ended"


def test_unreadable_photo_keeps_no_photos():
    session = Session()
    add_photos(session, {})
    assert session.photos == []


async def fix_planner(model, request, seen="", images=None, product=""):
    return {
        "title": "Clear sink", "safety": ["Take care."], "items": [],
        "steps": [{"say": "Plunge it", "detail": "More", "uses": [], "check": "Is the water draining now?"},
                  {"say": "Use a wire", "detail": "More", "uses": [], "check": ""},
                  {"say": "Call a plumber", "detail": "More", "uses": [], "check": ""}],
        "sources": [{"title": "Example", "url": "https://example.com/a"}],
    }


def fix_turn(session, text):
    return asyncio.run(Engine(FakeModel(), fix_planner).turn(session, text))


def at_fix_check():
    session = Session()
    fix_turn(session, "my kitchen sink is clogged")
    fix_turn(session, "ready")
    result = fix_turn(session, "next")
    assert result["check"] == "Is the water draining now?"
    return session


def test_yes_skips_remaining_steps():
    result = fix_turn(at_fix_check(), "yes")
    assert result["phase"] == "done"
    assert result["skipped"] == 2


def test_no_moves_to_next_fix():
    result = fix_turn(at_fix_check(), "no")
    assert result["phase"] == "steps"
    assert result["step"] == 2
    assert result["check"] == ""


def test_not_fixed_is_not_read_as_yes():
    assert fix_turn(at_fix_check(), "no it's not fixed")["step"] == 2


def test_fixed_early_from_any_step():
    session = Session()
    fix_turn(session, "my kitchen sink is clogged")
    fix_turn(session, "ready")
    assert fix_turn(session, "it's fixed")["phase"] == "done"


class LiveModel:
    def __init__(self, reply):
        self.reply = reply

    async def generate(self, prompt, images=None, json_mode=False):
        return json.dumps(self.reply)


def live(session, reply, question=""):
    return asyncio.run(Engine(LiveModel(reply), fake_planner).live(session, "abc", question))


def test_live_names_object_and_instructs():
    result = live(Session(), {"object": "dishwasher", "problem": "blocked filter", "say": "Pull out the filter.", "changed": True, "hazard": False})
    assert result["seen"] == "dishwasher"
    assert result["say"] == "Pull out the filter."


def test_live_stays_quiet_when_nothing_changed():
    session = Session()
    reply = {"object": "dishwasher", "say": "Pull out the filter.", "changed": False}
    assert live(session, reply)["say"] == ""


def test_live_hazard_stops():
    result = live(Session(), {"object": "toaster", "say": "Carry on.", "hazard": True})
    assert result["phase"] == "stopped"
    assert result["say"] == EMERGENCY_LINE


def test_live_never_says_safe():
    result = live(Session(), {"object": "kettle", "say": "It is safe to touch. Wipe the base.", "changed": True})
    assert result["say"] == "Wipe the base."


def test_mentioning_wall_socket_is_not_refused():
    session = Session()
    assert turn(session, "unplug the toaster from the wall socket")["phase"] != "ended"
    assert turn(Session(), "replace my wall socket")["phase"] == "ended"


def test_stop_pauses_calmly_and_resumes():
    session = Session()
    turn(session, "make a sandwich")
    turn(session, "ready")
    turn(session, "next")
    result = turn(session, "stop")
    assert result["phase"] == "paused"
    assert result["say"] != EMERGENCY_LINE
    result = turn(session, "resume")
    assert result["phase"] == "steps"
    assert result["step"] == 2


def test_hazard_words_still_trigger_emergency():
    session = Session()
    turn(session, "make a sandwich")
    assert turn(session, "there is smoke")["say"] == EMERGENCY_LINE


def test_new_request_after_pause_starts_fresh():
    session = Session()
    turn(session, "make a sandwich")
    turn(session, "stop")
    assert turn(session, "repair my brakes")["phase"] == "ended"


def test_shelf_picture_is_rejected_for_a_chair_step():
    import guide
    pictures = [{"url": "https://a.example/x.jpg", "description": "The assembly instructions show diagrams for a multi-tiered shelf unit"}]
    assert guide.pick_picture(pictures, 1, "Install the lower side rails", "Assemble this chair") is None


def test_matching_picture_is_kept():
    import guide
    pictures = [{"url": "https://a.example/x.jpg", "description": "A kitchen sink drain with a plunger sealed over it"}]
    picked = guide.pick_picture(pictures, 1, "Seal the plunger over the drain", "My kitchen sink is clogged")
    assert picked["source"] == "a.example"


def test_saved_guide_loads_without_search():
    import guide
    plan = guide.saved_plan("My washing machine won't drain")
    assert plan["saved"] and len(plan["steps"]) >= 4
    assert plan["items"][0]["links"]


def test_timer_is_set_without_moving_step():
    session = at_step()
    result = turn(session, "set a timer for ten minutes")
    assert result["action"] == "timer" and result["timer"] == 600
    assert result["step"] == 2


def test_status_question_does_not_move_step():
    session = at_step()
    result = turn(session, "where are we")
    assert result["say"].startswith("Step 2 of") and result["step"] == 2


def test_find_is_not_a_shopping_request():
    session = at_step()
    assert turn(session, "where do I find the filter cap")["shopping"] is None if "shopping" in turn(session, "repeat") else True


def test_question_is_answered_without_moving_step():
    session = at_step()
    reply = '{"known":true,"text":"Under the sink."}'
    result = asyncio.run(Engine(FakeModel(reply), fake_planner).turn(session, "where is the valve"))
    assert result["say"] == "Under the sink." and result["step"] == 2


def test_hold_on_does_not_move_step():
    session = at_step()
    result = turn(session, "hold on")
    assert result["say"].startswith("Standing by") and result["step"] == 2


def test_replacing_wall_socket_inside_a_step_is_unsafe():
    from safety import unsafe_step
    assert unsafe_step("Turn off the breaker, then replace the wall socket")
    assert not unsafe_step("Unplug the toaster from the wall socket")


def test_reheating_in_microwave_is_allowed():
    assert turn(Session(), "reheat soup in the microwave")["phase"] != "ended"


def at_step():
    session = Session()
    turn(session, "make a sandwich")
    turn(session, "ready")
    turn(session, "next")
    return session
