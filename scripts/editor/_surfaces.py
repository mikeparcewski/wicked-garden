"""``wicked.editor/2`` surfaces (DES-EDITOR-PLUGIN-CONTRACT-001 §5): the declaration a protocol-2 editor makes for
its three surfaces (the card in the thread, the options tabs in the host panel, full screen), parsed strictly.

A line-for-line port of studio's ``src/editors/surfaces.ts`` (``parseSurfaces``, the word and bound rules, and
``canonicalSurfaces``), so garden's ``pack check``, the scaffold and the conformance run refuse exactly what the
host refuses. Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from decimal import Decimal

LIMITS = {"actions": 4, "tabs": 5, "controls": 12, "options": 8, "label_chars": 24, "max_chars": 200,
          "values": 16, "card_min_px": 120, "card_max_px": 560}

ID_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")
# ASCII letters and digits, space and `·-'`; 1 to 24 characters (no other script: a look-alike cannot be spelled).
LABEL_RE = re.compile(r"[A-Za-z0-9 ·'-]{1,24}")
# A word mixing letters and digits ("1nstall", "Mp4") is refused: a digit can stand in for a letter.
MIXED_RE = re.compile(r"[A-Za-z][0-9]|[0-9][A-Za-z]")

# The host's decision words: only host-owned controls may use them (§5.2).
DECISION_WORDS = ("approve", "accept", "deliver", "merge", "send", "launch", "delete", "remove", "stop", "deny",
                  "allow", "grant", "install")
CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "κ": "k",
    "ι": "i", "μ": "m",
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
}
CONTROL_TYPES = ("toggle", "segmented", "select", "color", "text", "range")
ASPECTS = ("16:9", "4:3", "auto")
VERBS = ("plugin", "host:export", "host:ask")
MODES = ("simple", "advanced")


class SurfacesError(ValueError):
    """The declaration is refused, with the host's reason."""


def skeleton(label: str) -> list[str]:
    """NFKD, combining marks dropped, lower case, look-alikes folded, split on anything not a letter."""
    folded = "".join(ch for ch in unicodedata.normalize("NFKD", label) if not unicodedata.category(ch).startswith("M"))
    folded = "".join(CONFUSABLES.get(ch, ch) for ch in folded.lower())
    return [w for w in re.split(r"[^a-z]+", folded) if w]


def uses_decision_word(label: str) -> bool:
    """A word that STARTS with a decision word ("Approved", "ApproveAll") is refused; "Shallow" is not."""
    return any(word.startswith(w) for word in skeleton(label) for w in DECISION_WORDS)


def _is_num(v) -> bool:
    """A finite JSON number. A huge integer is what JavaScript reads as Infinity: not finite (never a crash)."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(float(v))
    except OverflowError:
        return False


def _label(v, where: str) -> str:
    if not isinstance(v, str) or not LABEL_RE.fullmatch(v):
        raise SurfacesError(f"{where}: a label is 1 to {LIMITS['label_chars']} plain characters")
    if MIXED_RE.search(v):
        raise SurfacesError(f"{where}: a word in a label is letters or digits, not both")
    if uses_decision_word(v):
        raise SurfacesError(f'{where}: "{v}" uses a word only the host\'s own controls may use')
    return v


def _id(v, where: str) -> str:
    if not isinstance(v, str) or not ID_RE.fullmatch(v):
        raise SurfacesError(f"{where}: a bad id")
    return v


def _obj(v, where: str) -> dict:
    if not isinstance(v, dict):
        raise SurfacesError(f"{where}: not an object")
    return v


def _only(o: dict, keys: tuple, where: str) -> None:
    for k in o:
        if k not in keys:
            raise SurfacesError(f'{where}: unknown field "{k}"')


def _unique(items: list, where: str) -> None:
    seen: set = set()
    for it in items:
        if it["id"] in seen:
            raise SurfacesError(f'{where}: the id "{it["id"]}" is used twice')
        seen.add(it["id"])


def _control(raw, where: str) -> dict:
    o = _obj(raw, where)
    _only(o, ("id", "label", "type", "options", "min", "max", "step", "maxChars"), where)
    c = {"id": _id(o.get("id"), where), "label": _label(o.get("label"), where)}
    kind = o.get("type")
    if kind not in CONTROL_TYPES:
        raise SurfacesError(f"{where}: an unknown control type")
    c["type"] = kind
    if kind in ("segmented", "select"):
        opts = o.get("options")
        if not isinstance(opts, list) or not 2 <= len(opts) <= LIMITS["options"]:
            raise SurfacesError(f"{where}: {kind} needs 2 to {LIMITS['options']} options")
        listed = []
        for i, op in enumerate(opts):
            w = f"{where}.options[{i}]"
            if not isinstance(op, dict):
                raise SurfacesError(f"{w}: a bad id")
            oid = _id(op.get("id"), w)
            olabel = _label(op.get("label"), w)
            _only(op, ("id", "label"), w)
            listed.append({"id": oid, "label": olabel})
        _unique(listed, f"{where}.options")
        c["options"] = listed
    elif "options" in o:
        raise SurfacesError(f"{where}: only select and segmented take options")
    if kind == "range":
        lo, hi, step = o.get("min"), o.get("max"), o.get("step")
        if not (_is_num(lo) and _is_num(hi) and _is_num(step)):
            raise SurfacesError(f"{where}: range needs finite min, max and step")
        if not (lo < hi) or not (step > 0) or step > hi - lo:
            raise SurfacesError(f"{where}: range needs min < max and 0 < step ≤ max - min")
        if abs(lo) > 1e9 or abs(hi) > 1e9 or step < 1e-6 or (hi - lo) / step > 1e6:
            raise SurfacesError(f"{where}: range bounds are within ±1e9, step ≥ 1e-6, at most 1e6 steps")
        if step < max(abs(lo), abs(hi)) * 1e-12:
            raise SurfacesError(f"{where}: range step is too fine for its bounds")
        c.update(min=lo, max=hi, step=step)
    elif any(k in o for k in ("min", "max", "step")):
        raise SurfacesError(f"{where}: only range takes min, max and step")
    if kind == "text":
        m = o.get("maxChars", LIMITS["max_chars"])
        integral = (isinstance(m, int) and not isinstance(m, bool)) or (isinstance(m, float) and m.is_integer())
        if not integral or not 1 <= m <= LIMITS["max_chars"]:
            raise SurfacesError(f"{where}: maxChars is 1 to {LIMITS['max_chars']}")
        c["maxChars"] = int(m)
    elif "maxChars" in o:
        raise SurfacesError(f"{where}: only text takes maxChars")
    return c


def _card(raw) -> dict:
    card = raw.get("card")
    if not isinstance(card, dict):
        raise SurfacesError("surfaces.card is required")
    _only(card, ("interactive", "aspect", "actions"), "surfaces.card")
    # Defaults apply only to an OMITTED field: an explicit null is a wrong type.
    interactive = card.get("interactive", False)
    if not isinstance(interactive, bool):
        raise SurfacesError("surfaces.card.interactive: a boolean")
    aspect = card.get("aspect", "16:9")
    if aspect not in ASPECTS:
        raise SurfacesError("surfaces.card.aspect: 16:9, 4:3 or auto")
    raw_actions = card.get("actions", [])
    if not isinstance(raw_actions, list) or len(raw_actions) > LIMITS["actions"]:
        raise SurfacesError(f"surfaces.card.actions: at most {LIMITS['actions']}")
    actions = []
    for i, a in enumerate(raw_actions):
        where = f"surfaces.card.actions[{i}]"
        a = _obj(a, where)
        _only(a, ("id", "label", "primary", "verb"), where)
        aid, alabel = _id(a.get("id"), where), _label(a.get("label"), where)
        verb = a.get("verb")
        if verb not in VERBS:
            raise SurfacesError(f"{where}: verb is plugin, host:export or host:ask")
        primary = a.get("primary", False)
        if not isinstance(primary, bool):
            raise SurfacesError(f"{where}: primary is a boolean")
        actions.append({"id": aid, "label": alabel, "primary": primary, "verb": verb})
    _unique(actions, "surfaces.card.actions")
    return {"interactive": interactive, "aspect": aspect, "actions": actions}


def _options(raw) -> dict | None:
    if "options" not in raw:
        return None
    o = _obj(raw["options"], "surfaces.options")
    _only(o, ("tabs",), "surfaces.options")
    raw_tabs = o.get("tabs")
    if not isinstance(raw_tabs, list) or not 1 <= len(raw_tabs) <= LIMITS["tabs"]:
        raise SurfacesError(f"surfaces.options.tabs: 1 to {LIMITS['tabs']}")
    tabs = []
    for i, t in enumerate(raw_tabs):
        where = f"surfaces.options.tabs[{i}]"
        t = _obj(t, where)
        _only(t, ("id", "label", "render", "controls"), where)
        tab = {"id": _id(t.get("id"), where), "label": _label(t.get("label"), where)}
        render = t.get("render")
        if render not in ("plugin", "controls"):
            raise SurfacesError(f"{where}: render is plugin or controls")
        tab["render"] = render
        if render == "controls":
            rc = t.get("controls")
            if not isinstance(rc, list) or not 1 <= len(rc) <= LIMITS["controls"]:
                raise SurfacesError(f"{where}.controls: 1 to {LIMITS['controls']}")
            controls = [_control(c, f"{where}.controls[{j}]") for j, c in enumerate(rc)]
            _unique(controls, f"{where}.controls")
            tab["controls"] = controls
        elif "controls" in t:
            raise SurfacesError(f"{where}: a plugin-rendered tab has no controls")
        tabs.append(tab)
    _unique(tabs, "surfaces.options.tabs")
    return {"tabs": tabs}


def _full(raw) -> dict | None:
    if "full" not in raw:
        return None
    f = _obj(raw["full"], "surfaces.full")
    _only(f, ("modes", "default"), "surfaces.full")
    modes = None
    if "modes" in f:
        if f["modes"] != list(MODES):
            raise SurfacesError('surfaces.full.modes: exactly ["simple","advanced"]')
        modes = list(MODES)
    default = f.get("default", "simple")
    if default not in MODES:
        raise SurfacesError("surfaces.full.default: simple or advanced")
    if modes is None and "default" in f:
        raise SurfacesError("surfaces.full.default needs modes")
    return {"modes": modes, "default": default}


def parse_surfaces(raw) -> dict:
    """Parse a ``surfaces`` declaration strictly; any violation refuses the whole of it (``SurfacesError``)."""
    raw = _obj(raw, "surfaces")
    _only(raw, ("card", "options", "full"), "surfaces")
    return {"card": _card(raw), "options": _options(raw), "full": _full(raw)}


def js_number(v) -> str:
    """A number as JavaScript's ``JSON.stringify`` writes it (ECMAScript Number::toString): the shortest round-trip
    digits, plain decimal for exponents -6..20, otherwise ``d.ddde±n``."""
    if isinstance(v, int) and not isinstance(v, bool) and abs(v) < 10 ** 21:
        return str(v)
    x = float(v)
    if x == 0:
        return "0"
    sign, digits, exp = Decimal(repr(abs(x))).normalize().as_tuple()
    ds = "".join(map(str, digits))
    k, n = len(ds), len(ds) + exp  # value = 0.ds × 10^n
    if k <= n <= 21:
        out = ds + "0" * (n - k)
    elif 0 < n <= 21:
        out = ds[:n] + "." + ds[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + ds
    else:
        e = n - 1
        out = (ds if k == 1 else ds[0] + "." + ds[1:]) + "e" + ("+" if e > 0 else "-") + str(abs(e))
    return ("-" if x < 0 else "") + out


def _js_json(v) -> str:
    """``JSON.stringify`` of plain data (dict, list, str, bool, None, number), no spaces, keys in insertion order."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return js_number(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(_js_json(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + _js_json(x) for k, x in v.items()) + "}"


def canonical_surfaces(s: dict) -> str:
    """The canonical JSON of parsed surfaces (fixed field order, defaults filled): studio's ``canonicalSurfaces``."""
    def control(c: dict) -> dict:
        out = {"id": c["id"], "label": c["label"], "type": c["type"]}
        if c.get("options") is not None:
            out["options"] = [{"id": o["id"], "label": o["label"]} for o in c["options"]]
        if c.get("min") is not None:
            out.update(min=c["min"], max=c["max"], step=c["step"])
        if c.get("maxChars") is not None:
            out["maxChars"] = c["maxChars"]
        return out

    def tab(t: dict) -> dict:
        out = {"id": t["id"], "label": t["label"], "render": t["render"]}
        if t.get("controls") is not None:
            out["controls"] = [control(c) for c in t["controls"]]
        return out

    card = s["card"]
    body = {
        "card": {"interactive": card["interactive"], "aspect": card["aspect"],
                 "actions": [{"id": a["id"], "label": a["label"], "primary": a["primary"], "verb": a["verb"]}
                             for a in card["actions"]]},
        "options": None if s.get("options") is None else {"tabs": [tab(t) for t in s["options"]["tabs"]]},
        "full": None if s.get("full") is None else {"modes": s["full"]["modes"], "default": s["full"]["default"]},
    }
    return _js_json(body)


def check_declaration(protocol, surfaces, present: bool) -> str | None:
    """The manifest rule (§8.2): ``surfaces`` is required when ``protocol`` includes 2 and refused when it doesn't.
    Returns the refusal, or None."""
    speaks2 = isinstance(protocol, list) and 2 in protocol
    if speaks2 and not present:
        return "a protocol-2 editor declares its surfaces (card, and optionally options and full)"
    if not speaks2 and present:
        return "surfaces are a protocol-2 field: add 2 to protocol, or drop surfaces"
    if not present:
        return None
    try:
        parse_surfaces(surfaces)
    except SurfacesError as exc:
        return str(exc)
    return None
