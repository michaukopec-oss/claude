# Post-match card runbook

What a scheduled session does, unattended, when a match it was told to watch
finishes. Pre-match cards are not covered here — those are generated on demand
and downloaded by hand.

## Preconditions

- `FUSSBALLDATEN_TOKEN` in the environment. Never print it. The header is
  `Authorization: <token>` with **no** `Bearer` prefix — `Bearer` returns 401,
  as do `X-Auth-Token` and `X-API-Key`.
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

6. **Write the copy** with `result_copy.build_copy(payload, hashtags)`
   (`result_copy.py`). Returns `instagram`, `facebook` and `x` text plus the
   `angles` it chose. The X variant is length-checked and falls back to
   score-plus-angle if the scorer lines would break 280 characters.

7. **Gate the export URL** with `expiry_gate.py` before scheduling anything.
   Canva export URLs live roughly 1.5-2 hours. `response-expires` in the query
   string is authoritative; `X-Amz-Date` is not reliable.

8. **Publish via Buffer.** Post-match is time-critical, so publish immediately
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
- **Own goals appear in both scorer lists.** The scoring player is listed under
  the team that *benefited*, and again under their own team for any real goal
  they scored. In Bayern 5:1 Stuttgart, Vagnoman appears on both sides. Copy
  must carry the `ET` flag or the same surname reads as two goals for two
  different teams in one post. `result_copy._scorers()` handles this.

## Autonomy

Publishing **is** autonomous, by the user's decision of 2026-09-18: on a
completed run the session publishes immediately to Instagram, Facebook and X
without waiting for approval. Scope is one match per kickoff slot, not all nine.

This makes the gates the only thing between bad data and a live post, so none
of them are advisory:

- `ready(payload)` must be true — status `post` **and** a populated full-time
  score.
- Every club in the fixture must resolve to a `canva_asset_id`.
- The rendered thumbnail must be checked against the payload score before the
  transaction is committed.
- At kickoff+120 with no ready payload: abandon, notify, publish nothing.

Any gate that fails is a stop and a notification, never a best guess.

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

## Scheduling: why the runs are self-bind wake-ups

A fresh-session Routine (`create_trigger` with `create_new_session_on_fire`)
**cannot** do this job on this account. Two findings, 2026-09-18:

- The `connectors` parameter is rejected outright: *"the connectors parameter
  is not available for this organization."*
- Creating the Routine without it succeeds but stores `mcp_connections: []`,
  and the tool warns that the fired session will run with no `mcp__*` tools.

A session with no Canva and no Buffer cannot build or publish anything, so that
route was abandoned rather than left to fail at fire time.

What is used instead: `send_later`, which schedules a message back into a
session that already holds both connectors. Its delivery survives container
restarts. One wake-up per match, fired at kickoff+105, carrying the fixture id,
the hashtag set and the cutoff.

The trade-off is a single point of failure: every run of the matchday depends
on that one session still being reachable. If it is not, nothing publishes and
nothing is corrupted — it fails closed.

The durable fix, when a whole season is scheduled rather than one matchday, is
to create the Routines from the claude.ai Routines UI, where connectors can be
attached to a fresh-session Routine. Do that before scaling past one matchday.

### Fire times

    fire   = kickoff + 105 min
    cutoff = kickoff + 120 min

Matchday 4, one match per kickoff slot:

| fixture | match | fire (UTC) |
|---|---|---|
| 883113 | Bayern – Union Berlin | Fri 20:15 |
| 883118 | Hamburg – Köln | Sat 15:15 |
| 883114 | Stuttgart – Dortmund | Sat 18:15 |
| 883115 | Leverkusen – RB Leipzig | Sun 15:15 |
| 883120 | Schalke – Elversberg | Sun 17:15 |
| 883121 | Paderborn – Hoffenheim | Sun 19:15 |
