# Editorial policy

*Draft v0.1 — 2026-07-18*

## What gets a firm included

A firm is included when both are true:

1. **Body of work:** at least **three projects** in the experiential design
   space (per the roles in the schema vocabulary) verifiable from public
   sources. One-time entrants and firms whose experiential work is incidental
   to an unrelated core business are not listed until they cross this bar.
2. **Identifiability:** the firm and its credits can be verified from public
   sources (firm portfolio, institutional announcements, award records, press).
   We do not publish credits we cannot source.

**What counts as a source.** A source must be a **public, independently
checkable record** — a live web page anyone can go look at. A firm's own
published website or portfolio page counts (it's public even if
self-authored). A claim that only exists as something told to us
privately, an internal or paywalled document nobody else can open, or a
page that returns an error for every reader — does not count, and the
fact it would support is dropped rather than published on that basis
alone. Every fact in the index traces to a source meeting this bar; there
is no "trust us" tier of inclusion.

There is no fee, no submission requirement, and no relationship prerequisite
for inclusion. Firms are added because their work belongs in the record.

**Current geographic scope:** firms headquartered in **North America** (the
United States or Canada). This is a participation test, not a residency
test — it exists to exclude firms that don't meaningfully participate in
the North American experiential-design industry, not to exclude
Canadian firms, which count fully alongside US ones. Firms headquartered
elsewhere and credited on North American projects appear in credits and
receive records as coverage expands. **Venue scope follows the same
line**: US and Canadian venues/projects are both in scope; other
countries are not yet.

**Venue scope:** the index covers designed experiences in public cultural
destinations (museums, science centers, attractions) and in institutional
settings — academic, healthcare, corporate, and civic spaces with
public-facing experiential installations. A venue does not need to be a
standalone public destination for its projects to be part of the record.
**Employee-only corporate workplace interiors are out of scope**: an office
its own staff experiences is not a public-facing designed experience. The
line is audience, not client industry — a company's briefing center,
experience center, or lobby installation that receives visitors is in
scope; its internal workplace is not.

**What "North America-based" means:** a firm's operating reality governs, not
its legal registration. A firm whose verifiable current operations (staff,
projects, published presence) run from the United States or Canada is
North America-based; a firm operating from elsewhere is not, even if a US
or Canadian legal entity persists. Where the public record leaves a firm's
North American presence genuinely uncertain, the firm's activity status
says so (see below) rather than the index guessing.

**Project-type scope: no advertising.** The index does not cover
advertising campaigns, ad-agency work, or one-off marketing/brand
activations (TV/digital commercials, social campaigns, marketing stunts).
This is a deliberate exclusion, not an oversight — advertising credit
rosters are notoriously incomplete and rarely publicly documented, which
runs directly against the sourcing standard above. The line is drawn by
the *nature of the engagement*, not the client's industry: a firm's work
on a **built, physical space** — a brand experience center, a corporate
museum, a retail flagship — stays in scope and is held to the same
sourcing bar as museum work, because those are still credited,
documented, physical installations. The same firm's ad-campaign work for
the same client is out of scope.

**Project-type scope: built work only.** The index records projects that
resulted in a built, installed experience. Master plans, feasibility
studies, and strategy engagements that produced a plan without a built
outcome are not recorded as projects — deliberately: they are often
unpublished (against the sourcing standard) and the index's promise is
who *built* what. The planning disciplines themselves remain fully
represented through their credits on built projects.

## Activity status (active vs. inactive firms)

Every firm record carries an evidence-based activity status — `active`,
`unclear`, or `inactive` — with the **basis** (what evidence) and a
**verification date** stated on the record. Definitions live in
[`schema/vocabularies.yaml`](../schema/vocabularies.yaml); in short, `active`
requires public evidence within the last 3 years (completed or announced
projects, award entries, hiring, publications), and `inactive` means confirmed
closure or 5+ years without public activity.

Inactive firms are **not removed** — their credits are part of the historical
record — but status is displayed prominently so a reader researching firms to
hire is never misled by a portfolio from a studio that no longer exists.

## Accuracy and corrections

- Every factual claim carries a source on the record.
- Anyone can submit a correction by opening an issue in this repository.
  Corrections from credited firms and institutions are prioritized and
  typically resolved within two weeks.
- Corrections that change credits are noted in the record's git history,
  which serves as the public changelog.

## Self-inclusion disclosure

The index is published and maintained by **Sitara Systems**, which is also a
listed firm. Sitara Systems appears under the same inclusion criteria,
sourcing standards, and activity-status methodology as every other firm.
Every ranked or curated list that includes Sitara Systems carries this
disclosure inline.

## Ranked lists

*Methodology adopted 2026-07-18 (v1).*

Ranked lists are published **per delivery-stack role** ("Top Exhibit Design
Firms," "Top AV Integration Firms," …) — never as a single cross-role master
ranking. The roles in the schema vocabulary describe different crafts serving
different buyer decisions; ranking an architecture firm against a fabrication
shop would manufacture a comparison that doesn't exist in practice.

Scores are computed **entirely from the open dataset by the formula below**,
with no subjective or reputational input, so any reader can reproduce any
list from the published data:

- **Eligible work:** completed projects only (`status: completed`), with
  `year_completed` in the trailing five years. Announced and in-progress
  work appears in the index but never counts toward a score.
- **Recency-weighted count:** each eligible project where the firm holds the
  list's role scores 1.0 if completed this year or last, 0.75 if 2–3 years
  ago, 0.5 if 4–5 years ago.
- **Sourcing bonus:** +0.1 per project (capped at +0.5 per firm) for
  projects corroborated by independent sources — meaning at least two
  distinct source domains not operated by the credited firm.
- **Ties** are broken by most recent `status_verified` date — never by
  editorial discretion.
- **Minimum depth:** a role receives a ranked list only once at least 8
  firms show eligible activity in it. Below that, we publish an unranked
  "Firms Working In [Role]" roundup instead — a small dataset ranked is a
  false signal.

Weights and thresholds may be revised as the dataset grows; every revision
to this policy is recorded in the repository's history.

**Self-inclusion:** every list runs the same formula against the same open
data, including the publisher's own record, and carries the disclosure above
inline whether or not Sitara Systems places on it.
