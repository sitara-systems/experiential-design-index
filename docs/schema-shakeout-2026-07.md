# Schema shakeout — 2026-07-18

*Phase 1 exercise per the plan of record: prove the schema on real records
before scaling research. 3 firms, 5 projects, 5 venues, sourced from public
award/press records (not yet Sitara-attached — this is a mechanics test, not
seed research).*

## Dataset

Built around one loosely-connected real ecosystem — two 2025 SEGD Global
Design Award winners plus AV&C's back catalog — so credits and firms overlap
across projects the way real coverage will:

- **Firms**: Ayers Saint Gross (architecture, Baltimore), Plus And Greater
  Than (exhibit design, Portland), AV&C (media design / AV integration, NYC)
- **Projects**: Jack C. Taylor Visitor Center (Missouri Botanical Garden,
  2022), Harbor Wetland (National Aquarium, 2024), Building Stories
  (National Building Museum, 2024), The Brain Index (Jerome L. Greene
  Science Center / Columbia, 2016), Jane's Carousel Pavilion Show Control
  (Brooklyn Bridge Park, 2011)
- **Venues**: all five above

Every record cites live public sources (firm sites, institutional press,
SEGD/ArchDaily/press coverage). Facts not confirmed by more than one source
were left out rather than guessed — e.g. Plus And Greater Than's founding
year isn't published anywhere findable, so `founded` is simply omitted
(the field is optional).

## Validator built

`scripts/validate.py` — stdlib + PyYAML, no dependencies beyond that. Checks:
required fields, vocab-enum membership, id/filename match, cross-reference
integrity (`project.venue` → `data/venues/`, `credits[].firm` → `data/firms/`,
`firm.successor` → `data/firms/`), date/year sanity, and the
announced-vs-completed status/year_expected pairing rule. Warns (doesn't
error) on credited firms with no record yet — the schema explicitly allows
that as a to-do, so it can't be a hard failure. Run: `python scripts/validate.py`
(`--strict` also fails on warnings, for a pre-publish gate later).

## Findings — schema/vocab gaps this exercise surfaced

1. **`founded` year range was wrong.** The validator's original year bound
   started at 1950; Ayers Saint Gross traces to 1912 and that's an
   unremarkable founding date for an architecture firm in this space (many
   peer firms — SOM, HOK, etc. — are older still). **Fixed**: bound widened
   to 1800. Real bug the shakeout was built to catch.

2. **`venue_types` was missing a Botanical Garden / Arboretum entry.**
   Missouri Botanical Garden (and peers — NY Botanical Garden, Chicago
   Botanic Garden, Longwood Gardens — all active experiential-design
   commissioners) didn't fit any existing type. **Added**: `botanical-garden`
   to `schema/vocabularies.yaml`. Confident addition — this is a common,
   unambiguous venue category in the space, not an edge case.

3. **Two venues landed on `other` and stayed there — flagged, not resolved:**
   - **National Building Museum** — a design/architecture-focused museum.
     Existing types imply either fine art (`art-museum`) or heritage
     narrative (`history-museum`); neither fits. Candidates: add a
     `design-museum` type, or fold it into a broadened `art-museum` label.
     Low volume (probably a handful of venues total: Cooper Hewitt, Design
     Museum-type institutions) — worth a deliberate call rather than a
     shakeout-session guess.
   - **Jerome L. Greene Science Center** — a university research building
     with one public-facing lobby installation, not a standing public
     museum/science-center. This is a different kind of edge case: it's a
     *venue type that may not belong in the vocabulary at all* if "venue"
     is meant to denote a public-facing cultural destination. Recommend
     deciding whether university research-building lobbies are in scope
     before more of these show up (they will — corporate/academic lobby
     installations are a real segment of the space, e.g. AV&C's own
     portfolio is full of them).

4. **Multi-role credits on one project work cleanly.** Plus And Greater Than
   holds both `exhibit-design` and `interpretive-planning` on Building
   Stories — the schema's "one firm, multiple roles" case validated without
   any special-casing needed.

5. **The `credits[].firm` without a firm record" allowance earns its keep
   immediately** — every real project pulled in landscape architects,
   fabricators, and secondary architecture partners that aren't yet
   first-class firm records (Arbolope Studio, Michael Vergason Landscape
   Architects, Southside Design + Build, Ateliers Jean Nouvel). The warning-
   not-error behavior is correct: Phase 2 seed research will create these
   records over time; nothing here should block a project record from
   existing in the meantime.

## Not yet exercised

- `successor` field (no inactive/merged firm in this dataset)
- `announced` / `in-progress` project status (all five records are
  `completed`)
- `aka` on a venue, non-US `hq`/`location`

These are fine to leave for Phase 2 batches — they're straightforward paths
in the validator, not areas of schema ambiguity like the venue-type gaps
above.

## Open for editorial review

- Decide the National Building Museum / design-museum vocab question (item 3
  above) — recommend before Phase 2 volume research starts, since choosing
  late means re-tagging records.
- Decide whether academic/research-building lobby installations are in
  scope at all (item 3, second bullet) — shapes how much of AV&C-style
  corporate/campus work gets indexed.
