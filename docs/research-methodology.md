# Research methodology

*How records get added and updated. This is the "how" — the "what" (inclusion
criteria, sourcing standard, scope exclusions) lives in
[`editorial-policy.md`](editorial-policy.md) and is not repeated here.
Whenever this dataset needs updating — new firms, new projects, periodic
re-verification — start from this document rather than re-deriving process.*

## Two complementary discovery methods

The dataset is built by two methods that find different things and should
both run over time, not just once:

1. **Award-archive sweep** (top-down, high-signal, survivorship-biased).
   Work backward year by year through a juried award archive (SEGD Global
   Design Awards, AAM MUSE, TEA Thea, AIA, GACEP). High confidence — the
   projects are pre-curated for significance and usually well-documented —
   but only surfaces the subset of any firm's work that won an award in a
   given year. A firm's full body of work is invisible to this method.

2. **Tiered crawl / breadth-first partner search** (bottom-up,
   comprehensive). Described in detail below. Starts from the firms already
   in the dataset, reads each firm's *own* published portfolio (not just
   their award-winning projects), and follows the delivery-stack credit
   graph outward to newly-discovered partner firms, tier by tier.

Both methods write to the same schema and are subject to the same hard
rules (below). A project discovered by one method that turns out to already
exist via the other is the same record — dedupe by project identity
(venue + name + year), not by which method found it first.

## Hard rules (apply to every method, every session)

These are restated here for a single reference point; they're identical to
what's enforced in the seed-research process and should not drift between
this doc and any batch-specific instructions:

1. **Every fact traces to a public, independently checkable source.** A
   firm's own published portfolio page counts — it's exactly the source
   type the tiered crawl runs on. A page that errors for every reader, a
   paywalled report, or a private/unpublished claim does not count. See
   `editorial-policy.md` § "What counts as a source."
2. **Never guess.** Unknown optional field → omit it. Unclear or
   conflicting credit → leave it out and log it, don't pick a side.
   Institutional sources outrank a firm's self-description when they
   conflict.
3. **No Sitara Systems records** until the separate Proposal-Assets library
   review gate clears (see the master `ExperientialIndex/CLAUDE.md`).
4. **No new `vocabularies.yaml` values** without a deliberate editorial
   decision — use the closest existing fit (or `other`) and log the gap.
5. **No advertising work** — ad campaigns, commercials, brand activations
   with no built physical space are out of scope. See `editorial-policy.md`
   § "Project-type scope: no advertising." A firm's brand-experience-center
   *building* is in scope; its ad campaign for the same client is not.
6. **US-based firms only** get firm records for now (non-US firms appear
   unlinked in credits). Non-US venues currently can't be recorded at all —
   `scripts/validate.py` hard-requires a US `state` on every venue; this is
   a known gap (see Batch 1's flag log) to fix before the tiered crawl hits
   firms with substantial international portfolios.
7. **IDs are lowercase kebab-case, stable, and must match the filename.**
   Before creating a firm or venue record, check whether one already exists
   under a plausible id — the single most common failure mode in every
   batch run so far has been two independent research passes slugging the
   same real firm slightly differently (e.g. `cg-partners` vs.
   `c-and-g-partners`, `ewing-cole` vs. `ewingcole`). When in doubt, grep
   `data/firms/` and `data/venues/` for the firm/venue name before minting
   a new id.
8. **Firm-record promotion threshold: ≥3 credited projects.** A firm
   credited on fewer than 3 projects in the dataset stays as an unlinked
   credit (`note: "no firm record yet"`) — this is allowed by the schema
   and is not an error. Once a firm crosses 3, it should get a firm record;
   this can happen either within a single research pass (if that pass finds
   3+ projects for one firm on its own) or centrally as a reconciliation
   step after a batch (tally credits across the whole dataset, promote
   anything that newly crosses the bar). Batches 1 and 2 both used the
   central-reconciliation approach; either is fine.

## Award-archive sweep — process

1. Pick a source (SEGD/AAM/GACEP/TEA/AIA) and a year not yet swept for that
   source. `docs/sources.md` has the source list and method notes.
2. Pull that year's award winners. Filter: US venue only; built physical
   work only (drop purely-digital and strategy/research/planning
   categories); drop advertising per rule 5 above.
3. For each remaining project: find the venue (reuse if it already exists),
   find the full delivery-stack credit list (institutional press usually
   has the most complete roster — check beyond the award listing itself),
   write the project record.
4. Check every credited firm against `data/firms/` before minting a new id.
5. After the sweep: run `python scripts/validate.py`, fix any errors,
   reconcile id near-duplicates, tally credits and promote firms crossing
   the 3-project bar (rule 8), commit.

This is what Batches 1 and 2 of `Phase2_Seed_Research_Handoff.md` did (11
anchor firms, then SEGD 2020–2026) — see `phase2-research-log.md` for the
worked example and every gap/conflict/fix that came up in practice.

## Tiered crawl (breadth-first partner search) — process

The core idea: **the dataset's own firm list is a seed for a graph crawl**,
not a fixed list. Every project record's `credits` names other firms; those
firms have their own portfolios; those portfolios name still more firms.
Crawling this graph breadth-first — one full tier at a time, with a pause
and reconciliation between tiers — is how the dataset gets *comprehensive*
rather than just *award-winner-complete*.

**Tier 0** is whatever firms already have records (a moving target — check
`data/firms/` at the start of a crawl, don't hardcode a list from a prior
session). **Tier 1** is the result of crawling every Tier 0 firm's own
portfolio. **Tier 2** is the result of crawling every *new* firm discovered
in Tier 1's credits. And so on.

### Per-tier procedure

1. **List the tier's target firms.** For Tier 1, this is every firm
   currently in `data/firms/`. For Tier N>1, this is every firm that (a)
   was newly discovered as a credited partner during Tier N-1's crawl, (b)
   is not already in `data/firms/` or already crawled in an earlier tier
   (see the crawl log below), and (c) is a plausible design/production firm
   under the roles vocabulary (not a GC, individual, or engineering-only
   credit, which the roles vocabulary doesn't cover — see the recurring
   vocab-gap note in `phase2-research-log.md`).
2. **For each target firm, one research pass:** visit the firm's own
   website portfolio/work page(s). Read *every* project listed, not just
   ones that also won an award. For each project:
   - Check `data/projects/` first — if this exact project (same venue +
     name/year) is already recorded, skip it (or, if the existing record is
     missing credits this pass can now source, extend it rather than
     duplicate it).
   - If new: create the project + venue records per the usual schema and
     hard rules. Capture the FULL credit list as the firm's own page
     documents it — this is what makes the tiered crawl valuable: firm
     portfolio pages often name the whole delivery stack even when award
     listings don't.
   - **Extract every other firm named in credits** — this is the point of
     the exercise. Keep a running list per research pass.
3. **Report the discovered-partner list.** Each tier's research passes
   report back their new project/venue files *and* the deduped list of
   partner firm names they found that aren't already in `data/firms/`. The
   orchestrating session compiles these across all of that tier's passes
   into the candidate list for the next tier.
4. **Reconcile the tier**, same as an award-sweep batch: run the validator,
   fix id near-duplicates, tally credits, promote firms crossing the
   3-project bar, commit, update this doc's crawl log (below) with which
   firms were crawled in which tier and the resulting candidate list for
   the next tier.
5. **Pause.** Do not automatically start the next tier. The candidate list
   should be reviewed (a light plausibility pass — is this actually a firm
   worth crawling, or a GC/individual/one-off collaborator that shouldn't
   propagate the search further) before committing session time to crawling
   it. This also bounds what could otherwise be exponential growth in scope.

### Why pause between tiers

The partner graph in this industry is dense — a single major project can
credit six or more firms, several of which are themselves multi-hundred-
project firms with their own extensive credit graphs. Left uncontrolled,
tier N+1's candidate list could be much larger than tier N's, and crawling
it fully could surface a large number of firms below the inclusion bar
(one-off collaborators, GCs, individual consultants) that add research cost
without adding index value. Pausing between tiers is a deliberate scale
control, not just a checkpoint — it's where a human (or a fresh session
with fresh judgment) decides whether the next tier's candidate list is worth
running in full, worth pruning, or worth running only against a subset.

### Crawl log

*Updated at the end of each tier. Each entry: tier number, date, firms
crawled, new projects/venues found, and the resulting next-tier candidate
list.*

- **Tier 1 — done (2026-07-18).** Crawled all 21 firms then in
  `data/firms/` (one agent per firm, run in parallel). Several agents
  (notably C&G Partners, Belle & Wissell, Northern Light Productions) fanned
  out further sub-agents on their own initiative to cover unusually large
  portfolios — a bigger fan-out than planned, but it stayed within one tier
  conceptually (still crawling only Tier-0 firms' own portfolios, not yet
  recursing into partners). Result: **dataset grew from 21/110/99
  (firms/projects/venues) to 39/473/388.** `validate.py`: 0 errors after
  reconciliation (fixed 5 firm-id near-duplicates —
  `art-guild`→`art-guild-inc`, `design-and-production`/
  `design-and-production-inc`→`design-and-production-incorporated`,
  `design-minds`→`the-design-minds`, `pure-applied`→`pure-and-applied`,
  `chicago-scenic`→`chicago-scenic-studios` — and 9 venue/project id
  collisions where a single-project venue's project record had taken the
  identical id, e.g. `walt-disney-family-museum` used by both; resolved by
  appending `-core-exhibits` to the project id, matching the corpus's
  existing `<venue>-<short-name>` convention).

  **Tier 2 candidate list**: after Tier 1, **76 firms** sit at ≥3 credited
  projects; **39 already have firm records** (21 original + 18 promoted
  mid-crawl by individual research agents: `esi-design`, `kubik-maltbie`,
  `gensler`, `available-light`, `cortina-productions`, `technical-artistry`,
  `skylab-architecture`, `history-associates`, `1220-fabrication`,
  `donna-lawrence-productions`, `northwest-sign-and-design`, `lmn-architects`,
  `mithun`, `graham-baba-architects`, `pacific-studio`,
  `imagine-visual-services`, `design-communications-ltd`, `videobred`). **37
  cross the bar without a record** — this is the literal Tier 2 candidate
  list (a firm needs a record before its own portfolio gets crawled, per the
  per-tier procedure above): `rlmg` is already a Tier-0 firm so excluded;
  remaining highest-value targets by credit count: `bbi-engineering` (9),
  `hadley-exhibits` (6), `cinnabar` (7), `luci-creative` (5),
  `ravenswood-studio` (5), `anita-jorgensen-lighting-design` (5),
  `populous` (5), `the-design-minds` (5), `dlr-group` (4), `hga` (4),
  `mystic-scenic` (4), `isometric-studio` (4), `tillotson-design-associates`
  (4), `skidmore-owings-and-merrill` (4), `rockwell-group` (4),
  `healykohler` (4), `west-office` (4), `southside-design-build` (10 —
  should have been promoted already per an agent's own report, wasn't
  found on disk; re-check), `design-and-production-incorporated` (10 —
  same discrepancy), plus 19 more at exactly 3 credits (`amaze-design`,
  `andrew-merriell`, `cambridgeseven`, `capitol-museum-services`,
  `chicago-scenic-studios`, `dangermond-keane-architecture`, `diversified`,
  `ennead-architects`, `ia-interior-architects`, `lexington`,
  `main-street-design`, `mass-design-group`, `pgav-destinations`,
  `ralph-appelbaum-associates`, `solid-light`, `the-urban-conga`,
  `zenith-systems`). Full per-agent partner-discovery lists (hundreds of
  additional below-threshold names) are in each agent's report, not
  reproduced here — the ≥3 tally above is the actionable queue.

  **Paused here per instruction** — Tier 2 (crawling these 37 firms' own
  portfolios) has not started. Two housekeeping items before it does:
  (1) re-verify `southside-design-build` and `design-and-production-incorporated`
  — reports claimed promotion but no file exists on disk, likely lost to
  concurrent-write contention during the fan-out; (2) the validator's
  US-state-only limitation will bite harder in Tier 2 as the crawl reaches
  larger firms (Tellart, Gensler, NBBJ/ESI) with substantial non-US
  portfolios.

## Updating an existing record (not just adding new ones)

This methodology also covers maintenance, not only initial seeding:

- **Firm status re-verification.** `status_verified` dates age out — the
  editorial policy's `active` definition is evidence within a trailing
  3-year window, so a record verified in 2026 needs a fresh check by 2029
  at the latest, sooner if there's reason to think something changed (a
  firm stops publishing, a merger rumor surfaces, etc.). Same process as
  initial research: check for public evidence of activity, update
  `status`/`status_basis`/`status_verified`, cite the new source.
- **Credit corrections.** If a correction request comes in (per the
  editorial policy's corrections process) or a later research pass finds a
  conflict, fix the record directly — git history is the changelog, per
  policy. Don't create a duplicate record to capture a correction.
- **A firm's portfolio changes over time** (new projects added, old ones
  removed from their site). Re-crawling an already-recorded firm's
  portfolio periodically (not just once in Tier 1) is reasonable
  maintenance, especially for `active`-status firms — but isn't a new tier
  in the BFS sense, just routine upkeep. Track it the same way: check
  `data/projects/` before adding, cite sources, run the validator.

## Reconciliation checklist (run after every batch, every tier)

1. `python scripts/validate.py` — fix all errors; warnings for
   not-yet-recorded credited firms are expected and fine.
2. Grep for near-duplicate firm/venue ids (different casing, abbreviation,
   punctuation for what's plausibly the same real entity) — this has
   happened in every multi-agent batch run so far and is the single most
   common cleanup item.
3. Tally credits per firm id across `data/projects/`; promote anything at
   ≥3 that lacks a firm record (or note it for a deferred/dedicated
   promotion batch if the list is long — see `phase2-research-log.md`
   Batch 2 for the precedent of deferring a long tail rather than promoting
   everything in one pass).
4. Spot-check any source flagged as risky during research (403s, single-
   sourcing, paywalls) against the public-sourcing standard — see Batch 1's
   audit in `phase2-research-log.md` for the worked example and the kind of
   issue this step catches (a citation that doesn't actually name the firm
   it's attached to).
5. Commit with a message describing what was added/promoted/fixed and the
   resulting totals (firms/projects/venues, validator error count).
6. Update the workspace-level `phase2-research-log.md` (flags, judgment
   calls, vocab gaps) and this doc's crawl log if the batch was a tiered-
   crawl tier. Update `ExperientialIndex/CLAUDE.md`'s session log.
