"""Turn a postmatch payload into post copy for Instagram, Facebook and X.

`result_card.py` fills the graphic; this fills the caption. Nothing here is
written by hand at publish time, so the rule is strict: every sentence is
assembled from payload fields. No superlative that the payload cannot prove
("erster Saisonsieg", "schlechteste Abwehr der Liga") appears, because a
single fixture's data cannot support a league-wide claim and nobody reads
these before they go out.

Angles are chosen by `angles()` from the score pattern alone. They add colour
without adding facts.
"""

MAX_X_CHARS = 280


def _minute(raw):
    """'45+2\\'' -> '45.+2', '21\\'' -> '21.'"""
    m = raw.rstrip("'")
    if "+" in m:
        base, extra = m.split("+", 1)
        return f"{base}.+{extra}"
    return f"{m}."


def _scorers(team):
    """'Olise (55.), Vagnoman (57., ET)' — own goals flagged, never silent.

    A player who scored an own goal appears in the *benefiting* team's list,
    so the flag is what stops the same surname reading as two goals for two
    different sides in the same post.
    """
    out = []
    for s in team.get("scorers") or []:
        mins = ", ".join(_minute(m) for m in s["minutes"])
        out.append(f"{_surname(s['name'])} ({mins}{', ET' if s.get('ownGoal') else ''})")
    return ", ".join(out)


def _surname(name):
    return name.split()[-1]


def _last_goal_minute(d):
    """Highest goal minute in the match, or None. Used for the late-winner angle.

    `minute` is an int and stoppage time sits in a separate `addedTime`, so the
    two are added rather than parsed out of the label.
    """
    best = None
    for g in d.get("goals") or []:
        m = g.get("minute")
        if m is None:
            continue
        n = int(m) + int(g.get("addedTime") or 0)
        best = n if best is None else max(best, n)
    return best


def angles(payload):
    """Score-pattern tags. Every one is decidable from the payload alone."""
    d = payload["data"]
    sc, tags = d["score"], []
    gh, ga = sc["goalsHome"], sc["goalsAway"]
    margin = abs(gh - ga)

    if gh == ga:
        tags.append("draw")
    elif margin >= 3:
        tags.append("rout")
    elif margin == 1:
        tags.append("narrow")

    if min(gh, ga) == 0 and gh != ga:
        tags.append("clean_sheet")
    if gh + ga >= 5:
        tags.append("goalfest")

    # Comeback: whoever led at the break did not win.
    ht = sc.get("halftime")
    if ht and ":" in ht and gh != ga:
        hh, ha = (int(x) for x in ht.split(":"))
        if hh != ha:
            ht_leader = "home" if hh > ha else "away"
            if ht_leader != sc.get("winner"):
                tags.append("comeback")

    last = _last_goal_minute(d)
    if last is not None and last >= 85 and margin == 1:
        tags.append("late")

    # The winner saw less of the ball than the loser.
    if sc.get("winner") in ("home", "away"):
        w, l = (d["home"], d["away"]) if sc["winner"] == "home" else (d["away"], d["home"])
        pw, pl = (w.get("stats") or {}).get("possession"), (l.get("stats") or {}).get("possession")
        if pw is not None and pl is not None and pw < pl:
            tags.append("possession_paradox")

    return tags


_HEADLINE = {
    "comeback": "Dreht das Spiel nach Rückstand zur Pause.",
    "rout": "Ein deutlicher Sieg.",
    "late": "Die Entscheidung fällt spät.",
    "goalfest": "Torreich bis zum Schluss.",
    "clean_sheet": "Zu null.",
    "draw": "Punkteteilung.",
    "narrow": "Eine enge Angelegenheit.",
}


def _headline(tags):
    """First matching tag wins — ordered by how much it says about the match."""
    for t in ("comeback", "late", "rout", "goalfest", "clean_sheet", "draw", "narrow"):
        if t in tags:
            return _HEADLINE[t]
    return "Das Spiel ist gelaufen."


def _context(payload):
    d = payload["data"]
    f, sc = d["fixture"], d["score"]
    md = f.get("matchday")
    parts = [f"{md}. Spieltag" if md else None]
    if sc.get("halftime"):
        parts.append(f"Halbzeit {sc['halftime']}")
    att = f.get("attendance")
    if att:
        parts.append(f"{att:,}".replace(",", ".") + " Zuschauer")
    return " · ".join(p for p in parts if p)


def build_copy(payload, hashtags=""):
    d = payload["data"]
    f, sc, h, a = d["fixture"], d["score"], d["home"], d["away"]
    tags = angles(payload)
    home, away = h["teamNameShort"], a["teamNameShort"]
    line = f"{home} {sc['goalsHome']}:{sc['goalsAway']} {away}"
    hs, as_ = _scorers(h), _scorers(a)
    url = f.get("url", "")

    ig = [f"{line}", "", _headline(tags), "", _context(payload)]
    if hs or as_:
        ig += [""]
        if hs:
            ig.append(f"⚽ {home}: {hs}")
        if as_:
            ig.append(f"⚽ {away}: {as_}")
    ig += ["", "Wie habt ihr das Spiel gesehen? 👇"]
    if hashtags:
        ig += ["", hashtags]

    fb = [f"Endstand: {line}", "", _headline(tags), "", _context(payload)]
    if hs or as_:
        fb += ["", "Die Tore:"]
        if hs:
            fb.append(f"▪️ {home} – {hs}")
        if as_:
            fb.append(f"▪️ {away} – {as_}")
    sh, sa = (h.get("stats") or {}), (a.get("stats") or {})
    if sh.get("available") and sa.get("available"):
        fb += ["", "Die Zahlen zum Spiel:",
               f"▪️ Ballbesitz: {sh['possession']}% – {sa['possession']}%",
               f"▪️ Torschüsse: {sh['shots']['total']} – {sa['shots']['total']}"
               f" (davon aufs Tor: {sh['shots']['onGoal']} – {sa['shots']['onGoal']})"]
    if url:
        fb += ["", "Alle Daten zum Spiel:", url]
    fb += ["", "Euer Fazit?"]

    x = [line, "", _headline(tags)]
    if hs:
        x.append(f"⚽ {home}: {hs}")
    if as_:
        x.append(f"⚽ {away}: {as_}")
    if hashtags:
        x += ["", hashtags]
    x_text = "\n".join(x)
    if len(x_text) > MAX_X_CHARS:
        # Drop the scorer lines first — the score and the angle are the post.
        x_text = "\n".join([line, "", _headline(tags)] + ([""] + [hashtags] if hashtags else []))

    return {
        "angles": tags,
        "instagram": "\n".join(ig),
        "facebook": "\n".join(fb),
        "x": x_text,
    }
