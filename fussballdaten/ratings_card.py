"""Build a player-ratings ("Die Noten") card on the Endstand brand background.

There is no ratings brand template, so this starts from the Endstand one,
strips the parts that describe a scoreline between two clubs, and lays a
one-row-per-player list over the background that survives. Keeping the
template as the base is the whole point: the gradient, the paper texture,
the fonts and the footer logo then come from the brand rather than from a
guess at it.

German school grades run 1 (best) to 6 (worst), so a low number is good and
the colour ramp has to run the other way from a stats card's.
"""

PAGE = None  # set by the caller; locator ids are f"{PAGE}-{ELEMENT}"

# Kept from the template and re-used, rather than deleted and rebuilt.
REUSE = {
    "headline":   "LBhQW9ydxhKhM10G",
    "match_info": "LBKxyYH3wg4bZxCb",
    "home_name":  "LBnsxcXnHDmqYHKg",   # rotated -90 down the left edge
    "away_name":  "LBJ9dpS70sLwTwlg",   # rotated  90 down the right edge
}

# Everything that only makes sense for a two-club result card.
DROP = [
    "LB4jrnRJK4sb2Htt", "LBRyYz96WKm2Bt8d",          # the two crests
    "LBVfhWW1qrGPJtpv", "LBP6wvC5HCy3Dqfx",          # the 92px scoreline
    "LBcXWWyZv8wlpRPv", "LBGTkmLKpK0QMJS8",          # scorer lists
    "LBdcWk6lS8ZZJP1Q", "LBkR8vl5CzRD4zpl",          # the six stat rows
    "LBr5h9DCVb7BcX4L", "LBnJfdnT202XVW6Z",
    "LBCV9BTxF1k1lNT8", "LB5QyFpLKk6CM8Cv",
    "LBZkh7k6gZzRdjyl", "LB2gSpdTfQD2rCrs",          # their labels
    "LBVQ1CrF97lMwHTD", "LBLvRd2vs6hHMjp2",
    "LB5y4ybcw6vghYxW", "LBnMwYctpGSfGfCt",
    "LB4bZbVPp7kPqr0V", "LBl0Hczykfq7jhvp",          # and their values
    "LBLHsxSB2ZvyskyR", "LBl3BTkXv0C3GQ39",
    "LBXK9FW6r1KsjpDq", "LBpxxYnQQnXRmJyW",
    "LB01drMKgjxfVpmf", "LBGwrKMZ2YtP9p89",
    "LB0dSMqlWZ1XVJYX", "LBdG2hKcsHbmVv47",
    "LBVGcFGvhkmSGMw0", "LBkFSQBbgHvHSS3R",
]

BRAND_DARK  = "#2b6815"   # template's deep green
BRAND_MID   = "#509a33"   # template's lighter green
INK         = "#343434"   # template's body grey
ROW_BG      = "#ffffff"
ROW_EDGE    = "#dcdcdc"   # the body panel is #f9f9f9, so a plain white row needs an edge
SECTION_INK = BRAND_DARK  # labels sit on the template's near-white body panel

# A grade is the one number a reader looks for, so it carries the colour.
# Red is not in the brand palette; it is here because "5" has to be legible
# as bad at a glance and grey cannot carry that on its own.
GRADE_POOR = "#a32b2b"
GRADE_MEH  = "#7a7a7a"


def grade_colour(grade):
    v = float(grade.replace(",", "."))
    if v <= 2.5:
        return BRAND_DARK
    if v <= 3.5:
        return BRAND_MID
    if v <= 4.5:
        return GRADE_MEH
    return GRADE_POOR


def _row(page, top, name, grade, geom):
    """One player: a white plate, the name, and the grade in its colour."""
    left, width, height = geom["left"], geom["width"], geom["height"]
    pad, name_size, grade_size = geom["pad"], geom["name_size"], geom["grade_size"]
    return [
        {"type": "insert_shape", "page_id": page, "top": top, "left": left,
         "width": width, "height": height, "path": "M0 0H64V64H0z",
         "view_box_width": 64, "view_box_height": 64,
         "color": ROW_BG, "corner_rounding": 0,
         "stroke_color": ROW_EDGE, "stroke_weight": 1},
        {"type": "add_text", "page_id": page, "text": name,
         "top": top + (height - name_size * 1.2) / 2, "left": left + pad,
         "width": width - pad * 3 - geom["grade_w"]},
        {"type": "add_text", "page_id": page, "text": grade,
         "top": top + (height - grade_size * 1.2) / 2,
         "left": left + width - pad - geom["grade_w"],
         "width": geom["grade_w"]},
    ]


def operations(page, data, geom):
    """Delete the result-card furniture, then lay out the ratings."""
    ops = [{"type": "delete_element", "locator_id": f"{page}-{e}"} for e in DROP]

    ops += [
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['headline']}",
         "text": "Die Noten"},
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['match_info']}",
         "text": f"{data['competition']}\n{data['fixture']}"},
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['home_name']}",
         "text": data["home_name"]},
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['away_name']}",
         "text": data["away_name"]},
    ]

    top = geom["first_top"]
    for label, players in (("STARTELF", data["starting"]),
                           ("EINGEWECHSELT", data["subs"])):
        ops.append({"type": "add_text", "page_id": page, "text": label,
                    "top": top, "left": geom["left"], "width": geom["width"]})
        top += geom["label_h"]
        for name, grade, _ in players:
            ops += _row(page, top, name, grade, geom)
            top += geom["height"] + geom["gap"]
        top += geom["section_gap"]
    return ops


def format_ops(page, data, geom, added):
    """Second pass: `add_text` cannot set size or colour, so style by id.

    `added` is the list of locator ids the insert pass returned, in the same
    order the operations were sent -- so each player contributes three: the
    white plate first, then the name, then the grade. The plate is skipped.
    """
    ops, i = [], 0
    for label, players in (("STARTELF", data["starting"]),
                           ("EINGEWECHSELT", data["subs"])):
        ops.append({"type": "format_text", "locator_id": added[i],
                    "formatting": {"font_size": geom["label_size"], "color": SECTION_INK,
                                   "font_weight": "bold", "text_align": "start"}})
        i += 1
        for name, grade, _ in players:
            ops.append({"type": "format_text", "locator_id": added[i + 1],
                        "formatting": {"font_size": geom["name_size"], "color": INK,
                                       "font_weight": "bold", "text_align": "start"}})
            ops.append({"type": "format_text", "locator_id": added[i + 2],
                        "formatting": {"font_size": geom["grade_size"],
                                       "color": grade_colour(grade),
                                       "font_weight": "bold", "font_style": "italic",
                                       "text_align": "end"}})
            i += 3
    return ops


PORTRAIT = {"left": 150, "width": 780, "height": 58, "gap": 8, "pad": 26,
            "first_top": 200, "label_h": 42, "section_gap": 16,
            "name_size": 27, "grade_size": 30, "grade_w": 86, "label_size": 20}

LANDSCAPE = {"left": 210, "width": 560, "height": 44, "gap": 6, "pad": 20,
             "first_top": 190, "label_h": 32, "section_gap": 12,
             "name_size": 20, "grade_size": 22, "grade_w": 64, "label_size": 15}


# --- 1600x900 -------------------------------------------------------------
# The landscape Endstand template is a different design, so it has its own
# element ids. Fourteen rows will not fit in one column at a readable size,
# so the list runs in two: starters on the left, substitutes on the right,
# with the best and worst grade called out underneath to fill the column.

DROP_LANDSCAPE = [
    "LB4jrnRJK4sb2Htt", "LBRyYz96WKm2Bt8d",          # the two crests
    "LBVfhWW1qrGPJtpv", "LBP6wvC5HCy3Dqfx",          # scoreline and halftime
    "LBcXWWyZv8wlpRPv", "LBGTkmLKpK0QMJS8",          # scorer lists
    "LBnsxcXnHDmqYHKg", "LBJ9dpS70sLwTwlg",          # club names (horizontal here)
    "LBdcWk6lS8ZZJP1Q", "LBkR8vl5CzRD4zpl",          # the six stat rows
    "LBr5h9DCVb7BcX4L", "LBnJfdnT202XVW6Z",
    "LBCV9BTxF1k1lNT8", "LB5QyFpLKk6CM8Cv",
    "LBZkh7k6gZzRdjyl", "LB2gSpdTfQD2rCrs",          # their labels
    "LBVQ1CrF97lMwHTD", "LBLvRd2vs6hHMjp2",
    "LB5y4ybcw6vghYxW", "LBnMwYctpGSfGfCt",
    "LB4bZbVPp7kPqr0V", "LBl0Hczykfq7jhvp",          # and their values
    "LBLHsxSB2ZvyskyR", "LBl3BTkXv0C3GQ39",
    "LBXK9FW6r1KsjpDq", "LBpxxYnQQnXRmJyW",
    "LB01drMKgjxfVpmf", "LBGwrKMZ2YtP9p89",
    "LB0dSMqlWZ1XVJYX", "LBdG2hKcsHbmVv47",
    "LBVGcFGvhkmSGMw0", "LBkFSQBbgHvHSS3R",
]

LANDSCAPE = {"width": 560, "height": 46, "gap": 6, "pad": 18,
             "top": 170, "label_h": 34, "section_gap": 24,
             "name_size": 24, "grade_size": 26, "grade_w": 70, "label_size": 17,
             "columns": (220, 820)}


def extremes(data):
    """Best and worst grade in the squad, as (label, names, grade) pairs."""
    everyone = list(data["starting"]) + list(data["subs"])
    keyed = [(float(g.replace(",", ".")), n, g) for n, g, _ in everyone]
    best, worst = min(k[0] for k in keyed), max(k[0] for k in keyed)
    pick = lambda v: (", ".join(n.split()[-1] for k, n, _ in keyed if k == v),
                      next(g for k, _, g in keyed if k == v))
    return [("BESTE NOTE",) + pick(best), ("SCHWÄCHSTE NOTE",) + pick(worst)]


def _column(page, left, top, sections, geom):
    """A labelled stack of rows; returns the operations and the next free top."""
    ops = []
    for label, rows in sections:
        ops.append({"type": "add_text", "page_id": page, "text": label,
                    "top": top, "left": left, "width": geom["width"]})
        top += geom["label_h"]
        for name, grade in rows:
            ops += _row(page, top, name, grade,
                        dict(geom, left=left))
            top += geom["height"] + geom["gap"]
        top += geom["section_gap"]
    return ops, top


def landscape_operations(page, data, geom=LANDSCAPE):
    ops = [{"type": "delete_element", "locator_id": f"{page}-{e}"}
           for e in DROP_LANDSCAPE]
    ops += [
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['headline']}",
         "text": "Die Noten"},
        {"type": "replace_text", "locator_id": f"{page}-{REUSE['match_info']}",
         "text": f"{data['competition']}\n{data['fixture']}"},
    ]
    starters = [(n, g) for n, g, _ in data["starting"]]
    subs = [(n, g) for n, g, _ in data["subs"]]
    # Each highlight is its own one-row section, so the label says which it is.
    highlights = [(label, [(names, grade)]) for label, names, grade in extremes(data)]

    left_col, right_col = geom["columns"]
    a, _ = _column(page, left_col, geom["top"], [("STARTELF", starters)], geom)
    b, _ = _column(page, right_col, geom["top"],
                   [("EINGEWECHSELT", subs)] + highlights, geom)
    return ops + a + b
