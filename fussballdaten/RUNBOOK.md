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

A match is 110-120 minutes of wall clock: 90 + about 15 of halftime +
stoppage at both ends. The API populates postmatch within seconds of the
whistle — Bayern-Union flipped to `post` at kickoff+113:27.

    kickoff + 105 min   first wake — poll
    every 5 min         re-poll while status is still "pre" or "live"
    kickoff + 150 min   give up, notify, do not publish

**The cutoff is a give-up deadline, not a publish time.** The run publishes the
moment `ready()` is true, whichever minute that falls on; the cutoff only says
when to stop waiting. Raising it never delays a post that would have gone out
anyway — it only turns "published nothing" into "published a few minutes
later" for a match that runs long.

That is why it is +150 and not +120. The old +120 was written against an
estimate of "~105 minutes of wall clock", which is roughly ten minutes short:
it left seven minutes of margin on a match with no VAR review and no injury
delay, and one long stoppage would have thrown away a perfectly good report.
The abandonment case the cutoff was written for — a suspended match, an API
outage — does not resolve at +145 either, so the later deadline gives up
nothing.

The five matchday 4 runs armed before this change keep their +120 prompts;
everything created afterwards uses +150.

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
   score-plus-angle if the scorer lines would break 280 characters. The
   Instagram variant is capped at five hashtags (see below); X and Facebook
   take the full string.

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

   The exact call shape, because the required metadata is easy to miss and the
   error arrives only after the card is already built:

       create_post(
         channelId      = <one of the three above>,
         schedulingType = "automatic",
         mode           = "shareNow",
         text           = copy["instagram" | "facebook" | "x"],
         assets   = [{"image": {"url": <png export url>,
                                "metadata": {"altText": "<home> <score> <away>, "
                                             "<competition>, <matchday>. Spieltag"}}}],
         metadata = ...per service, see below
       )

   | service | required `metadata` |
   |---|---|
   | instagram | `{"instagram": {"type": "post", "shouldShareToFeed": false}}` |
   | facebook  | `{"facebook": {"type": "post"}}` |
   | twitter   | none |

   `altText` is required whenever an image carries a `metadata` object at all.
   Instagram and TikTok reject a post with no image asset.

## Failure modes

| condition | action |
|---|---|
| 409 "has not started yet" | normal before the whistle; keep polling |
| still not `ready()` at +120 | abandon, notify, publish nothing |
| club missing from manifest | stop and notify — never publish a card with a missing crest |
| `stats.available` false | card still builds; stat rows render "-" |
| export URL near expiry | re-export rather than publishing a dead link |

## Things that will bite

- **The live feed's score is not the result.** In Bayern-Union (MD4) the
  `status: live` payload read 7:0 at minute 89, 8:0 at minute 94, and the
  final `status: post` payload read 7:0 with seven goal entries running 1:0
  to 7:0 and the last on 76 minutes. A goal appeared in the live feed and was
  gone from the official record. Publishing on score alone would have put an
  8:0 card out. This is what `ready()`'s `status == "post"` check is for, and
  why no run may relax it to "the score looks final".


- **Instagram takes five hashtags, no more.** `result_copy.cap_hashtags()`
  trims the Instagram caption to `MAX_IG_HASHTAGS`, so an over-long hashtag
  string in a routine prompt still publishes. Hand-written copy has no such
  safety net: count them. The cap cuts from the end, so put the tags you
  cannot lose first — the brand tag included, even though the published
  posts happen to carry it last in a set of four.

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

## The Canva -> Buffer handoff is proven

Buffer takes an image only as a url it fetches itself, so the one step nothing
had ever exercised was whether Buffer's fetcher could read a signed Canva S3
export link. It can. On 2026-09-18 the Wolfsburg-Darmstadt pre-match card went
out live to all three channels straight from an export url, and every response
echoed the right dimensions (1080x1350 portrait to Instagram, 1600x900
landscape to Facebook and X) -- Buffer could only report those by retrieving
and inspecting the file.

The consequence is the expiry gate, not the fetch: Buffer reads the url at send
time, not at create time, so a scheduled post whose export has expired by then
publishes nothing. Publish now, or re-export before you schedule.

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

## Measured run timing (MD4, Bayern-Union)

Kickoff 18:30 UTC. Every figure below is from a logged timestamp, not an
estimate; `generatedAt` in the payload is the API's own clock.

| moment | UTC | from kickoff |
|---|---|---|
| wake-up fires | 20:15:35 | +105:35 |
| last `status: live` poll (minute 96) | ~20:23:05 | +113:05 |
| payload flips to `status: post` (`generatedAt`) | 20:23:27 | +113:27 |
| Instagram live | 20:26:21 | +116:21 |
| Facebook live | 20:26:37 | +116:37 |
| X live | 20:26:46 | +116:46 |

Ready to all three channels: **3 min 20 s**. Both designs had been created
from their templates during the wait, so a run that starts cold adds roughly
another minute.

The number that matters is not the publish time, it is **+113**: the API
published the result within seconds of the final whistle, and the whistle
itself came 113 minutes after kickoff (two halves, halftime, and about eight
minutes of stoppage). The cutoff at +120 left six minutes of slack on a match
with no injury delay and no VAR review. A match with either would miss it and
abandon a perfectly good report.

The cutoff is **kickoff+150** as of this measurement. Polling is nearly free
and the gates, not the clock, are what stop a bad post; the only thing +120
bought was throwing away results that arrive a few minutes late.

## What else the API carries

Beyond what the two cards use today:

- **Per-player ratings** — `lineup.starting[].ratingSpm` and
  `stats.averageRatingSpm` (Sportmonks). `ratingFd` is in the schema but was
  still null three weeks after MD1, so treat it as not available.
- **Lineups** — starting XI and bench with shirt number, position, captain
  flag, minutes played, goals, assists, cards, substitution minutes. The
  per-player `shots`/`passes`/`passAccuracy` fields were null in every
  fixture checked.
- **Events** — `goals` (with `goalType`, e.g. `penalty`, and a German
  `detail`), `cards` (with the reason, e.g. "Meckern"), `substitutions`, and a
  merged `events` list, all with `minuteLabel`.
- **Richer team stats than the card shows** — `shots` split into
  onGoal/offGoal/blocked/insideBox/woodwork, `bigChances` created and missed,
  `passes` total/successful/accuracy/key, `crosses`, tackles, interceptions,
  offsides, saves.
- **Head-to-head** — overall and per-venue records plus the last five meetings.
- **Standing** — rank, previous rank, rank change, W/D/L, goals, points.

Other endpoints (all `Authorization: <raw token>`):

| endpoint | gives |
|---|---|
| `/v2/competitions` | every competition and its id |
| `/v2/competition/{id}` | one competition's metadata |
| `/v2/competition/{id}/standings?season=` | the full 18-row table |
| `/v2/competition/{id}/fixtures?season=` | the season's fixtures |
| `/v2/competition/{id}/matchday?season=&matchday=` | one matchday's fixtures |
| `/v2/fixture/{id}` | the bare fixture |

`/v2/competition/{id}/matchday` **does** honour a `matchday` parameter, unlike
`/v2/fixtures`, which ignores it and always returns the current one.

Prematch additionally carries `topScorers` (goals, assists, matches per player)
and `absences` (reason, free-text info, since/until).

### Two fields arrive late

`ratingSpm` and `attendance` were both null in the payload the run published
from and both populated by the next morning. Anything built on them cannot run
at kickoff+115; it needs a second pass hours later, or the next day.

### Fire times

    fire   = kickoff + 105 min
    cutoff = kickoff + 150 min   (the MD4 runs below were armed at +120)

Matchday 4, one match per kickoff slot:

| fixture | match | fire (UTC) |
|---|---|---|
| 883113 | Bayern – Union Berlin | Fri 20:15 |
| 883118 | Hamburg – Köln | Sat 15:15 |
| 883114 | Stuttgart – Dortmund | Sat 18:15 |
| 883115 | Leverkusen – RB Leipzig | Sun 15:15 |
| 883120 | Schalke – Elversberg | Sun 17:15 |
| 883121 | Paderborn – Hoffenheim | Sun 19:15 |

All six are armed. Pre-match posts scheduled by hand in Buffer do not collide
with these — they are a different post about a different moment in the match,
so a hand-scheduled pre-match card is not a reason to stand a result run down.
