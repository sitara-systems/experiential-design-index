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
3. **Sitara Systems self-inclusion is Nathan-gated, case by case.** The
   Proposal-Assets library review gate (see the master
   `ExperientialIndex/CLAUDE.md`) still blocks that specific source
   wholesale. Separately, as of 2026-07-19, individual Sitara projects can
   be added directly when Nathan points at a specific source (e.g. the
   sitara-website case-study stubs) — but every hard rule on this page
   still applies in full, including independent corroboration beyond
   Sitara's own site and the North America venue-scope rule (this is what
   held Tate Modern out of the first pass, despite being Sitara's
   best-documented project — see `phase2-research-log.md` 2026-07-19).
   Don't add a Sitara credit on Sitara's say-so alone, and don't relax any
   rule because the firm is the index's own publisher.
4. **No new `vocabularies.yaml` values** without a deliberate editorial
   decision — use the closest existing fit (or `other`) and log the gap.
5. **No advertising work** — ad campaigns, commercials, brand activations
   with no built physical space are out of scope. See `editorial-policy.md`
   § "Project-type scope: no advertising." A firm's brand-experience-center
   *building* is in scope; its ad campaign for the same client is not.
6. **North America-based firms (US or Canada)** get firm records; firms
   headquartered elsewhere appear unlinked in credits until coverage
   expands further (revised 2026-07-18 — previously US-only; see
   `editorial-policy.md`). **Venue scope follows the same line**: US and
   Canadian venues/projects are both in scope, other countries are not
   yet. `scripts/validate.py`'s `check_place()` already supports non-US
   places generically (`country` field, `state` optional off-US) — no
   code change needed for Canadian records, just use `country: CA` and a
   province instead of `state`.
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
9. **Four scope exclusions settled 2026-07-19** (full rationale in
   `editorial-policy.md`): no ephemeral theatrical/live-event production
   work (Broadway, touring shows, galas, concert/conference stage sets);
   no repeated/templated installation programs (a design that repeats
   near-identically across many sites, vs. a genuinely bespoke project);
   no cruise ships (not a fixed North American venue); no multi-site
   public art or civic programs with no single anchor venue. These
   recurred across multiple firm-portfolio screens before being decided —
   don't re-flag them as open questions, just apply the exclusion.

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
  (1) re-verify `southside-design-build` and ~~`design-and-production-incorporated`~~
  — reports claimed promotion but no file exists on disk, likely lost to
  concurrent-write contention during the fan-out. **`design-and-production-incorporated`
  fixed 2026-07-18**: firm record created, its own portfolio crawled
  (d-and-p.com — 7 category pages), 19 new projects/13 new venues added, 4
  existing D&P-credited projects extended with the fabrication credit
  D&P's own page corroborates (Grammy Museum LA Live, Johnson & Johnson
  Our Story, World of Little League, Museum of the Bible), and all of
  D&P's stale "no firm record yet" notes cleaned up. The crawl also
  crossed the 3-project bar for four of D&P's exhibit-design partners
  (Christopher Chadbourne & Associates, The Design Minds, Evidence Design,
  The PRD Group), which were promoted to firm records in the same pass
  per rule 8; Reich+Petch also crossed the bar but was correctly left
  unlinked — its HQ is Toronto/New York, so rule 6 (US-firms-only for
  records) excludes it. Excluded from this pass for insufficient/
  conflicting public-source dates: National Museum of the United States
  Navy (D&P names it but no sourceable date for D&P's scope of work), Las
  Cruces Museum of Nature & Science (conflicting 2012/2014 relocation
  dates), and "A Gift of Love" at the Saint John Paul II National Shrine
  (no sourceable exhibit-opening date); Harley-Davidson's 100th
  Anniversary Open Road Tour was excluded as a traveling brand promotion
  with no fixed venue. southside-design-build remains unfixed;
  (2) the validator's US-state-only limitation will bite harder in Tier 2
  as the crawl reaches larger firms (Tellart, Gensler, NBBJ/ESI) with
  substantial non-US portfolios.

- **Award cross-reference sweep — done (2026-07-18).** Not a BFS tier —
  a second pass through three more award-archive sources (SEGD already
  covered in Batch 2), 2020–2025, one agent per source-year (18 agents):
  Communication Arts Design Competition (Environmental Graphics category),
  Fast Company Innovation by Design Awards (Spaces and Places / Experience
  Design / Urban Design categories — category names shifted year to year,
  each agent confirmed the actual names for its year), AAM MUSE Awards.
  **Finding: AAM MUSE has been dormant since 2023** — AAM's own site states
  the program went on hold that year to redesign three other award
  programs; the last real cycle was 2021 (22nd annual). Multiple
  independent agents confirmed this (checked AAM's site, the annual-meeting
  recap, and ruled out an unrelated same-named commercial "MUSE Design
  Awards" competition) rather than substituting a different source. Only
  2020 and 2021 produced real AAM MUSE data; 2022–2025 correctly returned
  nothing. **Communication Arts note**: commarts.com's public archive is
  the *finalist shortlist*, not a separate winners-only list — agents
  cross-checked shortlist entries against live `commarts.com/project/...`
  pages as the practical "did this actually publish as a winner" bar.

  Result: dataset grew from 39/473/388 to **47/526/437**
  (firms/projects/venues). 4 more firms promoted mid-sweep
  (Skidmore Owings & Merrill, Rockwell Group, Ennead Architects, Creo
  Industrial Arts, Populous — several already sat above the bar from
  Tier 1 and just got their file written here). Reconciliation fixed one
  more id near-duplicate (`kierantimberlake`→`kieran-timberlake`);
  `validate.py`: 0 errors, no venue/project id collisions.

  **Recurring finding across nearly every agent**: a substantial share of
  Communication Arts' and Fast Company's "Environmental Graphics"/"Spaces
  and Places" winners are **private corporate workplace interiors**
  (Oracle Austin, LinkedIn Omaha, Hudson River Trading, NHL Office, Asurion
  Gulch Hub, etc.) — consistently excluded as "not public-facing" by
  independent agents applying the same judgment call flagged as an open
  question in Batch 2. This keeps recurring and keeps costing real,
  well-documented work — worth Nathan making an explicit, written call
  rather than leaving it to each agent's independent judgment.

  **Resolved same day**: Nathan wrote the explicit call directly into
  `editorial-policy.md` ("Employee-only corporate workplace interiors are
  out of scope... the line is audience, not client industry") and a
  companion clarification on `[[what "US-based" means]]` (operating
  reality governs over legal registration — resolves the Tellart HQ
  ambiguity flagged back in Batch 1). Both are now written policy, not
  per-agent judgment calls.

- **Tier 2 — done (2026-07-18).** Researched and created firm records for
  the ~33 firms sitting at ≥3 credits without one (per the Tier 1 +
  award-cross-reference candidate list), then crawled each one's own
  portfolio per the standard per-tier procedure. Folded in the same
  session, per instruction: a **Communication Arts Interactive category
  sweep** (2020–2025, CA's "Environmental" sub-category — physical
  interactive installations/kiosks, as distinct from CA's Design
  Competition "Environmental Graphics" category already covered, and
  distinct from pure websites/apps) — the most directly relevant CA
  category to spatial/embodied-interface work.

  Several individual Tier 2 firm crawls fanned out further sub-agents on
  their own initiative to cover unusually large or geographically
  dispersed portfolios — most notably **Schuler Shook** (a theatrical/
  architectural lighting design firm), whose crawl alone surfaced dozens
  of performing-arts-center and museum lighting credits across the US and
  spawned roughly 20 further research sub-agents. This is the clearest
  example yet of why the per-tier pause matters: a single Tier-2 firm's
  crawl can rival an entire prior batch in scope. PGAV Destinations, West
  Office, Capitol Museum Services, and HGA also fanned out multi-agent
  sub-batches.

  **Result: dataset grew from 47/526/437 to 88/900/709**
  (firms/projects/venues). `validate.py`: 0 errors, 0 id collisions.
  Reconciliation this round: retried 6 firm-record agents that hit
  transient "model temporarily unavailable" errors
  (`dangermond-keane-architecture` — the firm has since rebranded to
  Bearing Architecture, recorded with the old name as `aka` — plus
  `zenith-systems`, `schuler-shook`, `solid-light`,
  `southside-design-build`, `tait`); fixed 8 more firm-id near-duplicates
  (`fuse-project`→`fuseproject`, `taylor-group`→`the-taylor-group`,
  `diamond-schmitt`→`diamond-schmitt-architects`,
  `gwwo`→`gwwo-architects`, `proun`→`proun-design`,
  `howard-plus-revis`→`howard-plus-revis-design`, `span`→`span-studio`,
  `eos-light-media`→`eos-lightmedia`); removed 3 project records that
  turned out to have no independently sourceable `year_completed` (a
  required field — the sourcing agent had flagged them as "should skip"
  in its own report but the files existed anyway, a real
  process-inconsistency worth watching for); fixed 1 missing year on an
  otherwise well-sourced record (Florence County Museum, 2014).

  **Next tier's candidate list has not yet been tallied.** The next
  session should re-run the `comm -23` diff (credited-firms-at-≥3 minus
  `data/firms/` contents) fresh before starting Tier 3 — several firms
  were already promoted mid-crawl as side effects this round (Ravenswood
  Studio, New England Technology Group, Trivium Interactive, Cortina
  Productions, Christopher Chadbourne & Associates, The Design Minds,
  Evidence Design, The PRD Group among them), so the stale list from this
  entry would overcount. Given how large Tier 2 already ran (nearly
  doubling Tier 1's growth), strongly consider pruning the Tier 3
  candidate list — by credit-count threshold or manual review — before
  crawling it in full.

- **Tier 3 — Arrowstreet firm crawl (2026-07-18).** Targeted single-firm
  crawl: Arrowstreet (Boston architecture/environmental-graphics firm) was
  already credited on 2 projects (Dillaway-Thomas House, Hildreth
  Elementary School) with no firm record. Created
  `data/firms/arrowstreet.yaml` (founded 1961, `architecture` +
  `graphics-wayfinding` + `exhibit-design` + `interpretive-planning` roles,
  active). Crawled the firm's full portfolio sitemap (~280 URLs) and
  filtered to museum/library/civic work with real experiential content —
  the bulk of the sitemap is unrelated commercial/residential/mall/office
  work, correctly excluded. Added **9 new projects** and **5 new venues**:
  Pilgrim Monument and Provincetown Museum wayfinding (2022), PAAM
  wayfinding/donor recognition (2006, alongside Machado and Silvetti
  Associates' renovation), and 4 Boston Public Library Central Library
  projects at different dates (Central Library Wayfinding 2014, Teen
  Central 2015, Book Mosaic 2016 — reusing the existing
  `mystic-scenic` fabrication credit, Special Collections Exhibit 2022
  alongside Finegold Alexander Architects), East Boston Branch Library
  environmental graphics (2013, alongside William Rawn Associates), Thayer
  Public Library Children's Room (2019), and a Newburyport Black History
  Initiative interpretive-panel installment (2023) on the Clipper City Rail
  Trail. Reused the existing `boston-public-library` venue record for the
  four BPL projects. Excluded as out of scope: Patriot Place and its
  signage/wayfinding sub-projects (a 1.3M-sf retail/entertainment/hotel
  development — the embedded Patriots Hall of Fame museum has no
  separately documented Arrowstreet exhibit-design credit distinct from
  the overall commercial development), the Massport kinetic garage facade
  (parking structure, not a public-facing cultural/civic venue), Joan and
  Irwin Jacobs Center for STEAM Education (school building; its one
  interactive element was designed by a third party, not Arrowstreet), and
  Artists For Humanity EpiCenter (architecture of a working studio
  building with no exhibit/interpretive-design credit beyond the building
  shell). New unlinked partner-firm credits (all below the 3-project bar):
  `machado-silvetti-associates`, `william-rawn-associates` (2 credits),
  `finegold-alexander-architects`. `validate.py`: 0 errors from this
  batch (dataset's 1 pre-existing error, on an unrelated Dark Sky
  Discovery Center record, is not from this work).

- **Tier 3 — remaining 21 firms (2026-07-18).** Continuation of the same
  Tier 3 batch as the Arrowstreet entry above (one agent per firm, run in
  parallel): Thinc Design, Pentagram, EOS Lightmedia, Taylor Studios,
  Stephen Saitas Designs, Pure+Applied, Xibitz, Split Rock Studios, Span
  Studio, Southern Custom Exhibits, Snøhetta, Proun Design, Peter Hyde
  Design, Parz Designs, Olson Kundig, Monadnock Media, MAD Systems, Full
  Point Graphics, Explus, Batwin + Robin Productions, Art Guild Inc.
  (Moment Factory and Reich+Petch were excluded from firm-record creation
  going in — both already confirmed non-US in earlier tiers.)

  **Result: dataset grew from 88/900/709 to 112/1160/882**
  (firms/projects/venues). `validate.py`: 0 errors.

  Notable per-firm findings: **EOS Lightmedia** — researched directly on
  its own site rather than assumed; confirmed Vancouver, BC headquartered
  (a genuine but subsidiary US presence in Orlando/NYC doesn't clear the
  operating-reality bar), so no firm record was created, matching rule 6 —
  correctly left as unlinked credits. **Snøhetta** — a deliberate
  US-qualification test case: Oslo-founded but a 22-year-old, ~70-person
  New York studio independently leading US museum/cultural work (Joslyn
  Art Museum credited "Snøhetta New York" specifically) cleared the
  operating-reality bar in `editorial-policy.md`; firm record created with
  `hq` set to the NY office. **Xibitz** — the brief's assumed Maryland HQ
  was wrong; the firm's own site and history page place it in Grand
  Rapids, MI since 1988 (stale data-broker listings were the source of the
  bad assumption) — corrected before the record was written. **Parz
  Designs** — a real, active fabrication business, but its own portfolio
  is 100% residential; its 3 museum credits all come from a partner firm's
  (Isometric Studio's) project pages, not its own. **Explus** — the
  dispatched research agent returned a thorough two-part report but never
  wrote any files; the orchestrating session used that research directly
  to write the firm record + 3 new sourced projects. The agent's report
  also caught a live sourcing problem: an existing project record
  (`nascar-hall-of-fame-engine-ar.yaml`) credited Explus with no
  corroboration anywhere (not on Explus's own site, no independent
  source) — removed per the "never guess" rule rather than left
  standing. **Proun Design** — by far the largest single-firm crawl this
  tier; the dispatched agent fanned out 5 of its own sub-batches to cover
  Proun's ~90-project portfolio (Baker Library/HBS, MIT, social-justice/
  civil-rights exhibitions, NPS sites, corporate lobbies), contributing
  roughly 60 new projects on its own — a bigger single-firm fan-out than
  even Schuler Shook in Tier 2.

  Firms promoted mid-crawl as side effects (per rule 8, found while
  crawling a different target firm's credits): `studio-gang` and
  `navillus-woodworks` (via Span Studio), `taylor-studios` and
  `peter-hyde-design` (also independent Tier 3 targets in their own
  right, additionally surfaced via Xibitz's credits),
  `wondercabinet-interpretive-design` (via the Proun Design batch,
  recorded `status: inactive` — no activity found on its Cargo Collective
  portfolio past 2012–2013).

  Reconciliation this round: no firm-id near-duplicates found (each
  agent's own dedup pass held this time — a first). One project/venue id
  collision fixed (Norway House Saga Center). Two vocabulary gaps
  surfaced but not self-resolved (logged for Nathan): (1) no
  `project_types` value fits a standalone master-planning-only engagement
  (Proun's Historic Mitchelville Freedom Park master-plan credit — parked,
  not recorded); (2) no clean role fits "museum consulting" as distinct
  from `interpretive-planning` (one Proun-credited project, left
  uncredited for that one firm rather than force a mapping).

  **Tier 4 candidate list**: 20 firms now sit at ≥3 credits without a
  firm record. 4 are already-confirmed non-US and correctly stay unlinked
  regardless of credit count (`eos-lightmedia`, `moment-factory`,
  `reich-petch`, `lord-cultural-resources`). The other 16:
  `ashton-design`, `beyer-blinder-belle`, `bluebird-graphic-solutions`,
  `bowen-technovation`, `davis-brody-bond`, `diller-scofidio-renfro`,
  `gehry-partners`, `goppion`, `hilferty-and-associates`,
  `kieran-timberlake`, `matter-architecture-practice`,
  `mills-whitaker-architects`, `neal-mayer`, `smithgroup`,
  `tod-williams-billie-tsien-architects`, `upswell`, `wb-inc`. Given three
  tiers of consistent, large per-tier growth (39→88→112 firms; 473→900→1160
  projects), the next session should treat this as a genuine pause point —
  confirm scope/scale intent with Nathan before launching Tier 4, per the
  methodology's own "pause between tiers" rationale.

- **North America scope expansion (2026-07-18).** Nathan changed the
  geographic scope rule: "US-based firms only" → **North America (US +
  Canada)**, for both firm eligibility and venue/project scope ("I mostly
  mean to exclude firms that don't meaningfully participate in the US
  industry, but Canadian firms definitely count"). Updated `editorial-policy.md`
  and hard rule 6 above accordingly. Immediately promoted the 4 firms this
  unblocked — all previously excluded as non-US despite sitting at ≥3
  US-project credits: **EOS Lightmedia** (Vancouver, BC — lighting
  design), **Moment Factory** (Montréal, QC — media/immersive design),
  **Reich+Petch** (Toronto, ON + New York, NY — architecture/exhibit
  design), **Lord Cultural Resources** (Toronto, ON — museum planning
  consultancy). Each got a full firm record and a portfolio crawl that,
  for the first time, included Canadian venues rather than excluding
  them. Schema/validator needed no changes — `check_place()` already
  supported non-US places generically (`country` field, province instead
  of `state`); Canadian venue records just needed to actually use that
  path.

  **Result: dataset grew from 112/1160/882 to 116/1267/974**
  (firms/projects/venues). EOS Lightmedia's crawl was the largest of the
  four — its own site is a React SPA with no server-side rendering, which
  defeated ordinary WebFetch; the agent located the underlying JSON API
  (`eos-backend-qdkcn.ondigitalocean.app/api/project/<id>`) via the site's
  JS bundle and pulled all project records reliably from there instead
  (worth remembering as a technique for other JS-heavy portfolio sites).
  Reich+Petch's crawl added 22 new Canadian/US projects — designrp.com
  has a sparser in-page collaborator-credit convention than most firm
  portfolio sites, so most of those projects carry only the Reich+Petch
  credit itself, with a few (Massey Hall, YouthLink Calgary,
  NCAR-Wyoming Supercomputing Center) naming a fuller delivery stack.
  Several leads across both crawls were correctly excluded on scope
  grounds rather than force-added: a Deloitte Montréal office wayfinding
  program and a Metro Vancouver government office (employee-only
  corporate/civic interiors), the Canadian Fossil Discovery Centre (a
  master-plan/feasibility deliverable, not yet built), multiple
  real-estate-developer sales/presentation centres (River Green, Station
  Square, Three Sisters, River District — all advertising-adjacent, no
  lasting public installation), and several private commercial-office
  lobby art pieces with no standalone public identity. `validate.py`: 0
  errors; no firm-id near-duplicates (one near-miss caught and resolved
  inline — `CDM2 Lightworks` correctly reconciled to the existing
  `cdm-lighting-design-group` id, same Vancouver firm, rather than
  minted as a duplicate). One orchestrating-session fix: a
  Richmond Olympic Experience credit (Richmond, BC — W3 Design Group +
  Eos Lightmedia, 2015) was fully researched by one sub-batch but never
  written to disk (a sequencing oversight the sub-agent flagged in its
  own report); added directly from that research.

  **New Tier 4 candidates**: `aldrichpears-associates` (Vancouver,
  Canadian — surfaced repeatedly across the EOS Lightmedia crawl),
  `holman-exhibits`, `jack-rouse-associates`, `storyline-studio` now sit
  at ≥3 credits, joining the 16 already-identified Tier 4 candidates from
  the Tier 3 close-out entry above (that list's 4 "non-US, stays
  unlinked" firms are now fully resolved — all 4 have records as of this
  entry).

- **Phase 2 Batch 5 — corporate-experiential half (2026-07-18).** First
  dedicated pass at brand experience centers, executive briefing centers,
  and corporate museums — a segment prior batches barely touched, since
  they filtered for museum/cultural keywords. Three parallel agents, each
  a different discovery method: (1) **GACEP** (gacep.com, the corporate
  briefing-center trade association) — turned out to be a lead-generation
  source only, not a credits archive: it names award-recognized centers
  and corporate clients but never design/build firms, so every credit
  still had to be independently sourced via press or the firm's own
  portfolio; (2) **general press sweep** — searched trade press
  (Interior Design, Contract, ExhibitCity News) for well-known corporate
  visitor/briefing centers by name; (3) **existing-firm gap-fill** — the
  most productive angle: revisited ~15 firms already in `data/firms/`
  (AV&C, Local Projects, Diversified, ESI Design, Gensler, kubik maltbie,
  TAIT, Moment Factory, and others) specifically for corporate-client
  case studies their earlier museum-focused crawl had skipped.

  **Result: dataset grew from 116/1267/974 to 117/1299/1000**
  (firms/projects/venues) — 33 new projects, 1 firm promoted (ZGF
  Architects, crossed the bar via the Illumina Executive Briefing
  Center). Confirms the "revisit existing firms for a different angle"
  technique is worth reusing — it out-produced both the new-source sweep
  (GACEP: 3 projects) and the cold press search (6 firms: 8 projects)
  combined, at roughly the same effort.

  Access-model note codified: several corporate centers (Toyota
  Experience Center Plano, Microsoft Experience Center One) are
  invite/escort-only rather than public walk-in, but receive real
  outside visitors (customers, dealers, press) — recorded in scope per
  editorial policy's "audience, not client industry" line, matching the
  precedent already set by the Toyota Mississippi Experience Center.

  Several strong leads were dropped for missing/unsourceable completion
  years rather than guessed (both Federal Reserve Bank money museums,
  Comcast Living Lab, EY-Nottingham Spirk, ABB Houston, Timken,
  ConocoPhillips, Victoria's Secret Vancouver, several GACEP-listed
  centers) — flagged as follow-up candidates if a dated source surfaces
  later. `validate.py`: 0 errors, no firm-id near-duplicates (two
  venue/project id collisions self-caught and fixed inline by the
  agents, matching the established `-building`/`-exhibition` suffix
  convention).

  **New Tier 4 candidates**: `group-delphi` and `jack-rouse-associates`
  (the latter now credited across multiple batches — Tier 3, corporate,
  and this batch) join the growing candidate list; still recommending a
  pause before running a full Tier 4 or Tier 5.

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

## Monthly expansion checklist

*The repeatable procedure for keeping the dataset growing after the initial
seed build. A fresh session (or Nathan) should be able to start here without
re-deriving anything — every step below points at the fuller process
description elsewhere in this doc or in `editorial-policy.md`.*

Run these five tracks roughly once a month, in the order below (each one
is bounded and produces a natural stopping point — don't feel obligated to
run all five in one sitting if time is short; picking up an unfinished
track next month is fine, just note where it stopped in `phase2-research-log.md`).

### 1. Promote the ready backlog (near-zero cost, do this first every time)

Firms already sitting at ≥3 credited-but-unlinked projects just need a
firm-record file written — no new research. Recompute the list fresh each
month (don't reuse an old one — the dataset moves):

```
# for each firm id credited on ≥3 projects with no data/firms/<id>.yaml:
grep -h "firm: " data/projects/*.yaml | sort | uniq -c | sort -rn
# cross-reference against data/firms/ to find which ids have no file
```

Dispatch in batches of ~8 per research agent (see any of the "Promote N
firms" agent prompts from `phase2-research-log.md`'s 2026-07-19 entries for
the exact prompt shape) — these are light, ~5-10 min/firm confirmation
passes (HQ, founding year, roles), not full crawls, since the credits are
already sourced. Watch for: individuals rather than firms (skip, per the
firms-only schema), duplicate ids for an already-recorded firm under a
different slug (reconcile, don't create a second record), and firms whose
North America operating presence is thin (apply the same
operating-reality test used for Snøhetta/Mecanoo/Goppion).

### 2. One award-archive sweep (new source or new year)

Pick the next not-yet-swept year for an existing source, or a source not
yet tried, from `docs/sources.md`. SEGD/AAM/TEA are annual-cycle awards —
check whether a new cycle has been announced since the last sweep before
assuming "already covered." Follow the award-archive sweep process above.

### 3. One tiered-crawl tier, or a segment-directory sweep

Alternate between these month to month rather than always doing the same
one — they find different things (see "Two complementary discovery
methods" above):

- **Tiered crawl**: recompute the current candidate list (firms at ≥3
  credits with no record whose own portfolio hasn't been crawled yet),
  pick a bounded batch (8-15 firms), run the per-tier procedure. Pause
  after — don't auto-chain into the next tier.
- **Segment-directory sweep**: the GACEP Solutions Partners pass (2026-07-19)
  is the template — a trade-association or industry-directory page listing
  vendors/firms in an underserved segment. Cross-reference against
  `data/firms/`, bounded research per new name, same corroboration and
  scope rules. Worth repeating periodically since directories add new
  listings over time, and worth running against other segments as they're
  identified (the corporate-experiential segment was the first; others —
  e.g. a themed-attraction trade body, a specific regional AIA chapter
  award, a museum-technology vendor directory — are candidates for future
  months, not yet run).

### 4. Per-firm re-verification, on a rolling basis (not every firm every month)

Don't re-run the full 20-batch, 150-firm portfolio screen monthly — that
was a one-time catch-up pass. Instead, each month, re-verify a small,
rotating slice:

- Any firm whose `status_verified` date is more than ~6 months old, oldest
  first (`grep -h status_verified data/firms/*.yaml | sort` gives the
  ordering).
- Any firm flagged in `phase2-research-log.md` as a "near-miss" (1-2
  credits short of the dataset bar) — a quick recheck for a new credit.
- Any firm with a scheduled `status: unclear` re-check window implied by
  its `status_basis` (e.g. "no activity found since X" entries approaching
  the 5-year inactive threshold).

### 5. Close out the month

1. `python scripts/validate.py` — 0 errors before committing anything.
2. Tally credits, promote anything newly crossing the 3-project bar (this
   overlaps with track 1 — running track 1 again at month-end catches
   anything the month's research pushed over the line).
3. Rebuild the site (`python scripts/build_site.py`) and spot-check the
   firm-count / directory-count numbers on the About page look sane.
4. Update `phase2-research-log.md` with what ran this month (which
   tracks, what was found, what's queued for next month) and
   `ExperientialIndex/CLAUDE.md`'s session log with a one-paragraph summary.
5. Commit. One commit per track is fine; squashing the whole month into one
   commit is also fine — match whatever granularity made sense for how the
   month's session(s) actually ran.

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
