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


# --- Canva edit operations -------------------------------------------------

# Element locator ids in the landscape templates (stable across designs created
# from them). Page prefix is supplied at call time.
FIELD_ELEMENTS = {
    "headline": "LBhQW9ydxhKhM10G", "match_info": "LBKxyYH3wg4bZxCb",
    "score": "LBVfhWW1qrGPJtpv",    "halftime": "LBP6wvC5HCy3Dqfx",
    "home_name": "LBnsxcXnHDmqYHKg", "away_name": "LBJ9dpS70sLwTwlg",
    "home_scorers": "LBcXWWyZv8wlpRPv", "away_scorers": "LBGTkmLKpK0QMJS8",
    "label_1": "LBZkh7k6gZzRdjyl", "label_2": "LB2gSpdTfQD2rCrs",
    "label_3": "LBVQ1CrF97lMwHTD", "label_4": "LBLvRd2vs6hHMjp2",
    "label_5": "LB5y4ybcw6vghYxW", "label_6": "LBnMwYctpGSfGfCt",
    "home_stat_1": "LB4bZbVPp7kPqr0V", "away_stat_1": "LBl0Hczykfq7jhvp",
    "home_stat_2": "LBLHsxSB2ZvyskyR", "away_stat_2": "LBl3BTkXv0C3GQ39",
    "home_stat_3": "LBXK9FW6r1KsjpDq", "away_stat_3": "LBpxxYnQQnXRmJyW",
    "home_stat_4": "LB01drMKgjxfVpmf", "away_stat_4": "LBGwrKMZ2YtP9p89",
    "home_stat_5": "LB0dSMqlWZ1XVJYX", "away_stat_5": "LBdG2hKcsHbmVv47",
    "home_stat_6": "LBVGcFGvhkmSGMw0", "away_stat_6": "LBkFSQBbgHvHSS3R",
}
LOGO_ELEMENTS = {"home_logo": "LB4jrnRJK4sb2Htt", "away_logo": "LBRyYz96WKm2Bt8d"}

# Crest slots in the 1600x900 landscape cards: (left, top, size).
LANDSCAPE_SLOTS = {"home": (481, 156, 158), "away": (961, 156, 158)}


def edit_operations(payload, manifest, page_id, slots=None):
    """Full edit-design operation list for one match.

    `manifest` is crests/manifest.json (teamId -> canva_asset_id + ratio).
    Crests are filled by asset id, then sized to their own aspect ratio and
    re-cropped — the crop must be reset explicitly, because an element's image
    box keeps its scale through a resize and would clip the mark.
    """
    slots = slots or LANDSCAPE_SLOTS
    d = payload["data"]
    ops = [
        {"type": "replace_text", "locator_id": f"{page_id}-{FIELD_ELEMENTS[k]}", "text": v}
        for k, v in build(payload).items() if k in FIELD_ELEMENTS
    ]
    for side in ("home", "away"):
        crest = manifest[str(d[side]["teamId"])]
        left, top, size = slots[side]
        g = fit_crest(crest["ratio"], left, top, size)
        loc = f"{page_id}-{LOGO_ELEMENTS[side + '_logo']}"
        ops += [
            {"type": "update_fill", "locator_id": loc, "asset_type": "image",
             "asset_id": crest["canva_asset_id"],
             "alt_text": f"{crest['name']} club crest"},
            {"type": "resize_element", "locator_id": loc, "preserve_aspect_ratio": False,
             "width": g["width"], "height": g["height"]},
            {"type": "position_element", "locator_id": loc,
             "top": g["top"], "left": g["left"]},
            {"type": "crop_media", "locator_id": loc, **g["crop"]},
        ]
    return ops
