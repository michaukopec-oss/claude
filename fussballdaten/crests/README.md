# Club crest pack

18 Bundesliga / 2. Bundesliga crests rendered at 512px wide from the
`svgLogo` field of the fussballdaten API (prematch + postmatch both expose it).

## Why these exist

The API's `logo` field only ever returns a 38x38 `thumb-` image. De-thumbing the
path (`/thumb/originale/thumb-X.png` -> `/originale/X.png`) yields 100x100, and
that is the ceiling — `/gross/`, `/big/`, `/500/` and the bare path all 403.

100x100 is too small for the 148px crest slots in the Canva cards, and most club
marks are not square: fussballdaten pads them into a 100x100 box, so a wide
wordmark like Union Berlin (2.74:1) carries only ~100x36px of real artwork.

The vectors are sharp and correctly proportioned, but Canva will not accept them
at runtime: `update_fill` rejects vectors with "Only raster images can be used in
replacements", and `upload-asset-from-url` caps its `url` at 2048 characters, so a
`data:` URI cannot carry a usable PNG either.

So the crests are rendered once, here, and uploaded to Canva by hand. The pipeline
then maps `teamId` -> Canva asset id instead of fetching logos per match.

## manifest.json

Keyed by fussballdaten `teamId`:

    "282": {
      "name":  "1. FC Union Berlin",
      "file":  "1-fc-union-berlin.png",
      "w": 512, "h": 187,
      "ratio": 2.738,
      "svg":   "https://storage.fussballdaten.de/..."
    }

`ratio` is width/height. Use it to fit each crest inside the fixed slot rather
than stretching it to a square — see `fit_crest()` in `../result_card.py`.

Only 5 of the 18 are square. Range is 0.63 (Gladbach) to 2.74 (Union).

## Regenerating

    pip install cairosvg
    # pull svgLogo from /v2/fixture/{id}/prematch for each club, then:
    cairosvg.svg2png(bytestring=svg, output_width=512)
