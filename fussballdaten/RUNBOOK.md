# Post-match card runbook

What a scheduled session does, unattended, when a match it was told to watch
finishes. Pre-match cards are not covered here — those are generated on demand
and downloaded by hand.

## Preconditions

- `FUSSBALLDATEN_TOKEN` in the environment. Never print it.
- Canva and Buffer connectors authorized.
- `crests/manifest.json` current: every club in the fixture must have a
  `canva_asset_id`. A missing club is a stop, not a guess (see Failure modes).

## Timing

A match is ~105 minutes of wall clock: 90 + halftime + stoppage. The API
populates postmatch within a minute or two of the whistle.

    kickoff + 105 min   first wake — poll
    every 5 min         re-poll while status is still "pre" or "live"
    kickoff + 120 min   give up, notify, do not publish

The +120 cutoff is deliberate. If there is still no postmatch data half an hour
after a normal match would have ended, something is wrong — abandonment,
suspension, an API problem — and a card published on bad data is worse than no
card at all.

## Sequence

1. **Poll** `/v2/fixture/{id}/postmatch`.
   Before the whistle this returns HTTP 409 with
   `"Match has not started yet (status: pre). Use /prematch instead."` —
   that is a normal not-ready signal, not an error. Keep waiting.

2. **Gate on `ready(payload)`** (`result_card.py`). True only when
   `fixture.status == "post"` and `score.fulltime` is populated. Status alone
   is not enough; a finished fixture can briefly carry no score.

3. **Create the design** from the brand template:
   - X / Facebook  1600x900  `EAHVhv1Bmzo`
   - Instagram     1080x1350 `EAHVhlnTrIY`
   Note the returned design id and its page id.

4. **Apply** `edit_operations(payload, manifest, page_id)` in one
   `edit-design` call, then commit the transaction. 34 operations: 26 text,
   8 crest. Verify the returned thumbnail before committing.

5. **Export** as PNG. Do not send a `quality` field — the export endpoint
   rejects it with "Invalid MP4 quality value".

6. **Gate the export URL** with `expiry_gate.py` before scheduling anything.
   Canva export URLs live roughly 1.5-2 hours. `response-expires` in the query
   string is authoritative; `X-Amz-Date` is not reliable.

7. **Publish via Buffer.** Post-match is time-critical, so publish immediately
   rather than scheduling — the expiry gate then has hours of headroom instead
   of minutes.

   Channels (org `6aaa42d645b9b6ceabe5733b`):
   - Instagram `6aaa449aea19ca0bde55b96c`
   - Twitter/X `6aaa4396ea19ca0bde55b343`
   - Facebook  `6aaa432aea19ca0bde55b09a`

   Twitter rejects `notification` scheduling — use `automatic`.

## Failure modes

| condition | action |
|---|---|
| 409 "has not started yet" | normal before the whistle; keep polling |
| still not `ready()` at +120 | abandon, notify, publish nothing |
| club missing from manifest | stop and notify — never publish a card with a missing crest |
| `stats.available` false | card still builds; stat rows render "-" |
| export URL near expiry | re-export rather than publishing a dead link |

## Things that will bite

- **Reset the crop after every crest fill.** An element's image box keeps its
  scale through a resize, so a fill without `crop_media` clips the badge.
  `edit_operations()` already does this; do not "simplify" it away.
- **Crests are not square.** Ratios run 0.63 to 2.74. Forcing a square frame
  squashes 13 of the 18 clubs. `fit_crest()` handles it.
- **Never fetch logos from the API at runtime.** The `logo` field is a 38x38
  thumbnail and de-thumbing only reaches 100x100. Use the manifest's
  `canva_asset_id`.
- **Vectors cannot fill frames.** `update_fill` rejects them outright, and
  `upload-asset-from-url` caps its url at 2048 chars so a data URI cannot carry
  a real PNG either. This is why the crest pack is pre-rendered.
- **Publishing is not autonomous.** Nothing goes to a live channel without the
  user's explicit go-ahead for that run.

## Brand template editing is not available

`create-brand-template-draft`, and reading an existing brand template's
content, are refused for every template on this account — including ones the
user created by hand in the Canva UI:

    User does not have permission to access brand template with id '...'

Confirmed after a full disconnect/reconnect of the connector and a clean app
restart, against three separate templates of different origin. Metadata and
creation work fine (`search-brand-templates`, `get-brand-template-dataset`,
`publish-brand-template`), so this is Canva gating the content endpoints by
plan tier, not a scope or ownership problem. Do not retry it.

Consequence: the placeholder artwork inside a template can only be changed in
the Canva UI. This affects the thumbnail shown in the template list and nothing
else — every generated card is a fresh design created from the template, and
`edit_operations()` replaces both crests as part of the normal fill.

To update a template's design, edit it in Canva directly. Publishing a
corrected design through `publish-brand-template` would mint a *new* template
id and leave the old one behind, which is worse.
