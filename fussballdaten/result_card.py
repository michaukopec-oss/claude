"""Map a /v2/fixture/{id}/postmatch payload onto the Endstand template fields."""

MAX_SCORER_LINES = 5


def _scorer_lines(team):
    out = []
    for s in team.get("scorers") or []:
        surname = s["name"].split()[-1]
        mins = ", ".join(s["minutes"])
        out.append(f"{surname} {mins}" + (" (ET)" if s.get("ownGoal") else ""))
    if len(out) > MAX_SCORER_LINES:
        extra = len(out) - (MAX_SCORER_LINES - 1)
        out = out[: MAX_SCORER_LINES - 1] + [f"+{extra} weitere"]
    return "\n".join(out) or "–"


def _score_line(sc):
    """Full-time score, annotated for extra time / penalties."""
    base = f"{sc['goalsHome']} : {sc['goalsAway']}"
    if sc.get("penaltyShootout"):
        return base + "  i.E."
    if sc.get("extraTime"):
        return base + "  n.V."
    return base


def _stat(team, *path, suffix=""):
    st = (team.get("stats") or {})
    if not st.get("available"):
        return "–"
    v = st
    for k in path:
        v = (v or {}).get(k)
        if v is None:
            return "–"
    return f"{v}{suffix}"


def build(payload):
    d = payload["data"]
    f, sc, h, a = d["fixture"], d["score"], d["home"], d["away"]

    md = f.get("matchday")
    line1 = f["competition"]["name"].upper() + (f" · {md}. SPIELTAG" if md else "")
    venue = (f.get("venue") or {}).get("name", "")
    att = f.get("attendance")
    line2 = " · ".join(x for x in [venue.upper() if venue else None,
                                   f"{att:,}".replace(",", ".") + " ZUSCHAUER" if att else None] if x)

    fields = {
        "headline": "Endstand",
        "match_info": "\n".join(x for x in (line1, line2) if x),
        "score": _score_line(sc),
        "halftime": f"HALBZEIT {sc['halftime']}" if sc.get("halftime") else "",
        "home_name": h["teamNameShort"], "away_name": a["teamNameShort"],
        "home_scorers": _scorer_lines(h), "away_scorers": _scorer_lines(a),
        "label_1": "BALLBESITZ", "label_2": "TORSCHÜSSE", "label_3": "AUFS TOR",
        "label_4": "ECKEN",      "label_5": "FOULS",      "label_6": "PASSQUOTE",
    }
    spec = [("possession",), ("shots", "total"), ("shots", "onGoal"),
            ("corners",), ("fouls",), ("passes", "accuracy")]
    for i, path in enumerate(spec, 1):
        sfx = "%" if path[0] in ("possession",) or path[-1] == "accuracy" else ""
        fields[f"home_stat_{i}"] = _stat(h, *path, suffix=sfx)
        fields[f"away_stat_{i}"] = _stat(a, *path, suffix=sfx)
    return fields


def ready(payload):
    """Guard: only publish when the match is genuinely finished and scored."""
    d = payload["data"]
    return d["fixture"]["status"] == "post" and d["score"].get("fulltime") is not None


# --- crest placement -------------------------------------------------------
# Club marks are not square: the API pads them into a square box, and the
# vector originals range from 0.63 (Gladbach) to 2.74 (Union Berlin).
# Forcing them into a square frame either squashes them or leaves the artwork
# marooned in padding. Fit each one inside the slot instead.

def fit_crest(ratio, slot_left, slot_top, slot=148):
    """Geometry for one crest fitted inside a square slot, preserving aspect.

    `ratio` is width/height, from crests/manifest.json.
    Returns the element box to apply via resize_element + position_element,
    plus the crop box to pass to crop_media (resetting any inherited crop).
    """
    if ratio >= 1:                      # wide mark: full width, centred vertically
        w = slot
        h = slot / ratio
    else:                               # tall mark: full height, centred horizontally
        h = slot
        w = slot * ratio
    return {
        "width": round(w, 2),
        "height": round(h, 2),
        "left": round(slot_left + (slot - w) / 2, 2),
        "top": round(slot_top + (slot - h) / 2, 2),
        # crop_media must match the element exactly, or the image box keeps its
        # old scale and the mark gets clipped — the ratio survives a resize.
        "crop": {"top": 0, "left": 0, "width": round(w, 2), "height": round(h, 2)},
    }
