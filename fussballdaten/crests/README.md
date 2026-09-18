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

## Canva asset ids

Each entry now carries `canva_asset_id`. The crests were uploaded to the Canva
account's asset library via `upload-asset-from-url`, pointing at the raw
GitHub URLs in this directory — which also neatly sidesteps the 2048-char
`url` limit that ruled out data URIs.

They are named `fdcrest <teamId> <club>` so they group together when searched.

The pipeline fills a crest frame with `update_fill` using `canva_asset_id`,
then applies `fit_crest(ratio, ...)` from `../result_card.py` to size and crop
it. It never needs to upload anything per match.

Note: these live in the account's Uploads library, not inside the Fussballdaten
brand kit's "Graphics and components" panel (`kAHVeU_qTwI`). The Canva connector
exposes no write access to brand kit contents — `list-brand-kits` is read-only
and `create-brand-template-draft` is refused for lack of scope. Adding them to
the brand kit panel is a manual drag in the Canva UI. It makes no difference to
the automation, which addresses assets by id.
