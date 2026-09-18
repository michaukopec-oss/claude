# Routine prompt template — automated post-match report

Paste into the **Instructions** box at claude.ai/code/routines → **New routine**.
Change only the three marked lines per fixture.

## Routine form settings

| Field | Value |
|---|---|
| Name | `Post-match: <home> – <away>` |
| Repository | `michaukopec-oss/claude` |
| Environment | **Fussballdaten** — NOT Default (see below) |
| Trigger | Schedule → one-off run at kickoff + 105 min, local time |
| Connectors | keep **Canva** and **Buffer**, remove everything else |

The environment choice is not cosmetic. **Default** uses Trusted network access,
which allows only Anthropic's default domain allowlist — `api.fussballdaten.de`
is not on it, so every poll would fail with `403 host_not_allowed`. **Default**
also does not carry `FUSSBALLDATEN_TOKEN`. The **Fussballdaten** environment has
both. Connector traffic (Canva, Buffer) routes through Anthropic's servers and is
unaffected either way.

## Prompt

```
Automated post-match report: <HOME> vs <AWAY>, Bundesliga fixture <FIXTURE_ID>.   <-- CHANGE
Hard cutoff: <CUTOFF_UTC>.                                                        <-- CHANGE
Hashtags: "#Bundesliga <FIXTURE_HASHTAG> #<N>Spieltag #fussballdaten"             <-- CHANGE
          (four here on purpose: Instagram takes at most five, and the
           caption is trimmed to the first five if you add more)

You are running unattended and publishing live to real social channels. Nobody
reviews this before it goes out. Publish only if every gate passes.

STEP 0 — If the Canva or Buffer connector is unavailable, STOP, publish nothing,
and report that. Do not attempt a workaround.

STEP 1 — Check out branch `claude/fussballdaten-api-test-0ohkxu` and read
`fussballdaten/RUNBOOK.md` in full. Follow it. The modules you need
(result_card.py, result_copy.py, expiry_gate.py, crests/manifest.json) are in
that directory.

STEP 2 — Poll GET https://api.fussballdaten.de/v2/fixture/<FIXTURE_ID>/postmatch
with header `Authorization: $FUSSBALLDATEN_TOKEN` — raw token, NO "Bearer"
prefix (Bearer returns 401). HTTP 409 "has not started yet" is a normal
not-ready signal. If not ready, re-check every 5 minutes until the cutoff above,
then abandon and publish nothing.

STEP 3 — Gate: result_card.ready(payload) must be true (status "post" AND a
populated full-time score). Both clubs must resolve to a canva_asset_id in
crests/manifest.json. A missing club is a stop, never a guess.

STEP 4 — Build both cards. Apply result_card.edit_operations(payload, manifest,
page_id) in one edit-design call per design, and CHECK THE RENDERED THUMBNAIL
against the payload score BEFORE committing the transaction. A mismatch is a stop.
  Instagram 1080x1350  template EAHVhlnTrIY
  X / Facebook 1600x900 template EAHVhv1Bmzo  (pass result_card.LANDSCAPE_SLOTS)

STEP 5 — Copy: result_copy.build_copy(payload, hashtags=<HASHTAGS ABOVE>).
Use the returned instagram / facebook / x strings verbatim. Do not improvise
extra claims — the generator is deliberately limited to what one fixture proves.

STEP 6 — Export each design as PNG. Do NOT send a `quality` field (rejected with
"Invalid MP4 quality value"). Check each URL with expiry_gate.py; re-export
rather than publishing a link near expiry.

STEP 7 — Publish immediately. Buffer org 6aaa42d645b9b6ceabe5733b, mode
`shareNow`, schedulingType `automatic`, altText on every image:
  Instagram 6aaa449aea19ca0bde55b96c — portrait card  + copy["instagram"]
  Facebook  6aaa432aea19ca0bde55b09a — landscape card + copy["facebook"]
  X         6aaa4396ea19ca0bde55b343 — landscape card + copy["x"]

PUBLISH NOTHING and report if: not ready by the cutoff; a club is missing from
the manifest; the thumbnail score does not match the payload; or an export URL
cannot be refreshed.

Report what you published with links, or what stopped you.
```

## One match, one mechanism

A fixture must be owned by exactly one trigger. A web Routine and a `send_later`
wake-up pointed at the same fixture both publish, and the result is the same
post twice on all three channels. Before enabling a Routine for a match, delete
the wake-up for it (or vice versa) — checked with `list_triggers`, comparing
`next_run_at` values.

When fixing a Routine that currently collides, **change the schedule first and
the environment second**. In that order a half-finished edit is harmless: the
run either fires at the wrong time and fails closed on the environment, or does
not fire at all. In the other order, a fixed environment plus an unfixed
schedule is exactly the double-post.

Agents cannot edit a Routine created in the web UI — `update_trigger` refuses
with *"Agents can only update routines they created."* Web-created Routines are
edited by the user at claude.ai/code/routines, or disabled by their own run.

## Gotchas

- **Schedule stagger.** Routine runs "may start a few minutes after the
  scheduled time." Our fire-to-cutoff window is only 15 minutes, so set the
  one-off at kickoff+105 and set the cutoff in the prompt to kickoff+135 rather
  than +120, to keep the stagger from eating the whole polling window.
- **Daily routine cap.** Routine runs are capped per account per day. Six
  matches on one matchday is fine, all nine plus pre-match would need checking
  at claude.ai/settings/usage. One-off runs do not count against the cap;
  recurring ones do.
- **`/schedule` does not work from a cloud session.** The CLI hides it here.
  Create routines from the web UI, or from Claude Code on your own machine.
- **Runs act as you.** Posts publish through your linked Buffer account and
  appear as you, not as a bot.
