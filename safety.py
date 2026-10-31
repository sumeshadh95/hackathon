import re

EMERGENCY_LINE = (
    "Stop now. Move away from it. Only unplug it if that is safe. "
    "If anyone is in danger or there is a fire, call 112."
)

REFUSALS = [
    # Fault words, not the bare noun, so "reheat it in the microwave" still works for recipes.
    (r"\bmagnetron\b|\bmicrowave\b.*\b(won't|wont|isn't|isnt|not|stopped|broken|repair|sparks?|sparking|capacitor|fault|faulty|dead|fuse)\b"
     r"|\b(fix|repair|take apart|dismantle)\b.*\bmicrowave\b|\bopen (my |the |a )?microwave (oven )?(case|casing|cover)\b|\bopen up (my |the |a )?microwave\b",
     "The capacitor inside a microwave can hold a lethal charge even when unplugged. This one needs a qualified technician."),
    (r"\b(fix|repair|install|replace|connect|disconnect)\b.*\bgas\b|\bgas (pipe|line|connection|boiler|leak)\b",
     "Gas work can cause explosions and poisoning. Please call a qualified gas engineer."),
    # What the user is doing matters: "unplug it from the wall socket" is good advice.
    (r"\bmains wiring\b|\b(fix|repair|replace|install|rewire|wire)\b.*\b(wall socket|light switch|circuit breaker|fuse box|consumer unit|control board|mains)\b"
     r"|\b(wall socket|fuse box|consumer unit)\b.*\b(broken|sparks?|sparking|burnt|burned|scorched|faulty)\b",
     "Mains electrics can kill. Please call a qualified electrician."),
    (r"\b(swollen|bulging|leaking|punctured|damaged) (lithium |phone |laptop |tablet )?batter(y|ies)\b",
     "Don't charge it or keep working on it. Take it to a battery collection point or repair shop."),
    (r"\b(brake pads?|brakes|airbags?|steering|fuel lines?|fuel pump)\b",
     "A mistake here can cause a serious crash or fire. Please use a qualified mechanic."),
    (r"\b(ev battery|electric car battery|hybrid battery)\b|\b(open|repair|fix)\b.*\bhigh voltage\b",
     "High-voltage systems can kill. Please use a qualified technician."),
    (r"\b(under the car|jack up|jacking up)\b",
     "Working under a raised car can be fatal. Please use a garage."),
    (r"\b(medicine|medication) dos(e|age)\b|\boverdose\b",
     "Please ask a pharmacist or doctor about this."),
]

CAUTION_TERMS = [
    r"\b(phone|iphone|smartphone|tablet|ipad|laptop)\b.*\b(screen|display|battery)\b",
    r"\b(screen|display|battery)\b.*\b(phone|iphone|smartphone|tablet|ipad|laptop)\b",
]
CAUTION_LINE = (
    "This job means working next to a lithium battery, and a punctured battery can catch fire. "
    "It needs patience, steady hands and the right tools. Stop if the battery looks swollen. "
    "If you are comfortable with that, say I understand the risk. "
    "Otherwise, a repair shop is the safer choice."
)
CAUTION_CONFIRM = "i understand the risk"
SAFE_ADVICE = r"\b(unplug|switch off|turn off|isolate|call|ask|qualified|technician|electrician|do not|don't|never|avoid)\b"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", text.lower())).strip()


def wants_pause(text: str) -> bool:
    return re.fullmatch(r"(please )?stop( now| it| stop| that| talking| please)?", norm(text)) is not None


def is_emergency(text: str, active: bool) -> bool:
    n = norm(text)
    return active and re.search(
        r"\b(smoke|smoking|fire|burning|sparks?|sparking|shock|shocked|smell gas|gas leak)\b", n
    ) is not None


def unsafe_step(text: str) -> bool:
    # Checks each clause, so "turn off the breaker, then replace the wall socket" is still caught.
    clauses = re.split(r"[.;,:]|\band\b|\bthen\b", text.lower())
    return any(check_refusal(c) and not re.search(SAFE_ADVICE, norm(c)) for c in clauses)


def check_refusal(text: str) -> str | None:
    n = norm(text)
    return next((reason for pattern, reason in REFUSALS if re.search(pattern, n)), None)


def needs_caution(text: str) -> bool:
    n = norm(text)
    return any(re.search(pattern, n) for pattern in CAUTION_TERMS)


def confirms_caution(text: str) -> bool:
    return CAUTION_CONFIRM in norm(text)