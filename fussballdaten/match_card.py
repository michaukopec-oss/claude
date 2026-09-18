"""Map a /v2/fixture/{id}/prematch payload onto the Teamvergleich template."""

import re

from result_card import fit_crest

MONTHS_DE = None  # dates come pre-formatted from the API's `date` field

FIELD_ELEMENTS = {
    "headline": "LBhQW9ydxhKhM10G", "match_info": "LBlWxWhvGXc0D9dm",
    "home_name": "LBnsxcXnHDmqYHKg", "away_name": "LBJ9dpS70sLwTwlg",
    "home_form": "LB86dLFwPCly9FMS", "away_form": "LBNcKKVZC9fg6QVL",
    "home_coach": "LBVGcFGvhkmSGMw0", "away_coach": "LBkFSQBbgHvHSS3R",
    "label_1": "LBZkh7k6gZzRdjyl", "label_2": "LB2gSpdTfQD2rCrs",
    "label_3": "LBVQ1CrF97lMwHTD", "label_4": "LBLvRd2vs6hHMjp2",
    "label_5": "LB5y4ybcw6vghYxW", "label_6": "LBnMwYctpGSfGfCt",
    "home_stat_1": "LB4bZbVPp7kPqr0V", "away_stat_1": "LBl0Hczykfq7jhvp",
    "home_stat_2": "LBLHsxSB2ZvyskyR", "away_stat_2": "LBl3BTkXv0C3GQ39",
    "home_stat_3": "LBXK9FW6r1KsjpDq", "away_stat_3": "LBpxxYnQQnXRmJyW",
    "home_stat_4": "LB01drMKgjxfVpmf", "away_stat_4": "LBGwrKMZ2YtP9p89",
    "home_stat_5": "LB0dSMqlWZ1XVJYX", "away_stat_5": "LBdG2hKcsHbmVv47",
}
LOGO_ELEMENTS = {"home_logo": "LB4jrnRJK4sb2Htt", "away_logo": "LBRyYz96WKm2Bt8d"}


def _de_date(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def _signed(n):
    return f"+{n}" if n and n > 0 else str(n if n is not None else "–")


def _standing(team, key, fmt=str):
    st = team.get("standing") or {}
    v = st.get(key)
    return "–" if v is None else fmt(v)


def build(payload):
    d = payload["data"]
    f, h, a = d["fixture"], d["home"], d["away"]

    venue = (f.get("venue") or {}).get("name", "")
    # Some referee names carry a home-town suffix, e.g. "Tobias Stieler (Hamburg)".
    # The card has no room for it and it reads as noise next to the venue.
    ref = re.sub(r"\s*\(.*?\)", "", (f.get("referee") or {}).get("name", "")).strip()
    line1 = f["competition"]["name"].upper()
    if f.get("matchday"):
        line1 += f" · {f['matchday']}. SPIELTAG"
    line2 = " · ".join(x for x in [
        _de_date(f["date"]),
        f"{f['time']} UHR" if f.get("time") else None,
        venue.upper() or None,
    ] if x)
    lines = [line1, line2] + ([f"SCHIEDSRICHTER: {ref.upper()}"] if ref else [])

    fields = {
        "headline": "Teamvergleich",
        "match_info": "\n".join(lines),
        "home_name": h["teamNameShort"], "away_name": a["teamNameShort"],
        "home_form": "".join(h.get("form") or []) or "–",
        "away_form": "".join(a.get("form") or []) or "–",
        "home_coach": (h.get("coach") or {}).get("name", "–"),
        "away_coach": (a.get("coach") or {}).get("name", "–"),
        "label_1": "PUNKTE", "label_2": "TORE", "label_3": "TOR-\nDIFFERENZ",
        "label_4": "SIEGE", "label_5": "TABELLEN\nPLATZ", "label_6": "TRAINER",
    }
    spec = [("points", str), ("goalsFor", str), ("goalDifference", _signed),
            ("wins", str), ("rank", str)]
    for i, (key, fmt) in enumerate(spec, 1):
        fields[f"home_stat_{i}"] = _standing(h, key, fmt)
        fields[f"away_stat_{i}"] = _standing(a, key, fmt)
    return fields


def ready(payload):
    """Both teams need a league position for the comparison to mean anything."""
    d = payload["data"]
    return all((d[s].get("standing") or {}).get("rank") is not None
               for s in ("home", "away"))


def edit_operations(payload, manifest, page_id, frames):
    """Operations for one pre-match card.

    `frames` maps "home"/"away" to that design's current logo box
    {top,left,width,height}, read from the design itself — the portrait and
    landscape templates place their crests differently, so the slot is derived
    rather than hardcoded. The crest is fitted into a square centred on that box.
    """
    d = payload["data"]
    ops = [
        {"type": "replace_text", "locator_id": f"{page_id}-{FIELD_ELEMENTS[k]}", "text": v}
        for k, v in build(payload).items() if k in FIELD_ELEMENTS
    ]
    # One slot size for both sides, so neither crest dominates: the smaller of
    # the two frames. The portrait template still carries a wide wordmark frame
    # on the away side, which would otherwise blow that crest up.
    size = min(max(frames[s]["width"], frames[s]["height"]) for s in ("home", "away"))
    for side in ("home", "away"):
        crest = manifest[str(d[side]["teamId"])]
        box = frames[side]
        cx = box["left"] + box["width"] / 2
        cy = box["top"] + box["height"] / 2
        g = fit_crest(crest["ratio"], cx - size / 2, cy - size / 2, size)
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
