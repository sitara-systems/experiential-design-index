# Data schema

Three entity types, each one YAML file per record:

- `data/firms/<firm-id>.yaml`
- `data/projects/<project-id>.yaml`
- `data/venues/<venue-id>.yaml`

IDs are lowercase kebab-case slugs, stable once assigned (they become URLs).
Cross-references use these IDs. Enum fields draw from
[`vocabularies.yaml`](vocabularies.yaml). Blank templates with field-by-field
comments live in each `data/` subfolder (`_template.yaml`).

## Firm

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | slug | ✔ | Stable; matches filename |
| `name` | string | ✔ | Current legal/trade name |
| `aka` | list | | Former names, common abbreviations |
| `website` | url | | |
| `hq` | object | ✔ | `city`, `state` (US two-letter); `country` defaults to US |
| `other_offices` | list | | Same shape as `hq` |
| `founded` | year | | |
| `roles` | list of role ids | ✔ | What the firm does (delivery-stack roles) |
| `status` | firm_status id | ✔ | `active` / `unclear` / `inactive` |
| `status_basis` | string | ✔ | The evidence, e.g. "Completed X (2025); SEGD award entry 2026" |
| `status_verified` | date | ✔ | When the status was last checked |
| `successor` | firm id | | If merged/absorbed |
| `summary` | string | ✔ | 1–3 sentences, self-contained, factual |
| `sources` | list of urls | ✔ | Where the facts came from |

A firm's project list is derived from project credits — never duplicated on
the firm record.

## Project

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | slug | ✔ | Usually `<venue>-<short-project-name>` |
| `name` | string | ✔ | |
| `venue` | venue id | ✔ | |
| `project_type` | project_type id | ✔ | The scope proxy (new building → installation) |
| `year_completed` | year | ✔ | Opening year; `year_expected` for announced work |
| `status` | enum | | `completed` (default) / `announced` / `in-progress` |
| `credits` | list | ✔ | Each: `firm` (firm id), `role` (role id), optional `note` |
| `technologies` | list | | Free-text but consistent (e.g. "projection mapping", "RFID") |
| `technology_tags` | list of technology_tag ids | | Controlled differentiator tags (see vocabularies.yaml `technology_tags` — definitions + evidence bar). Only when the project's cited sources support the tag. |
| `platforms` | list of platform ids | | Commercial products/software the project was built on (see vocabularies.yaml `platforms`). Sources must name the product on this project; manufacturer deployment case studies count as sources. Not a credit — manufacturers are never credited firms. |
| `recognition` | list | | Juried awards won by this project. Each: `award` (e.g. "SEGD Global Design Awards — Honor Award"), `year`, `source` (url). Juried/curated programs only — no pay-to-enter "badge" schemes. |
| `summary` | string | ✔ | Opening sentence must answer "who built what, where, when" self-contained |
| `description` | string | | Longer prose |
| `sources` | list of urls | ✔ | |

Every credit names both the firm and its role — the full delivery stack is
the point. A credited firm without a record in `data/firms/` is allowed
temporarily (rendered unlinked) but is a to-do.

## Venue

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | slug | ✔ | |
| `name` | string | ✔ | |
| `venue_type` | venue_type id | ✔ | |
| `location` | object | ✔ | `city`, `state`; `country` defaults to US |
| `operator` | string | | Owning institution/brand if distinct from name |
| `website` | url | | |
| `annual_attendance` | object | | Most recent publicly reported annual visitorship: `figure` (integer), `year` (reporting year), `source` (url — institutional report, AAM, TEA/AECOM Museum Index, etc.). Record only published figures; never estimate. |
| `sources` | list of urls | | |
