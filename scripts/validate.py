#!/usr/bin/env python3
"""Validate data/{firms,projects,venues}/*.yaml against schema/schema.md and
schema/vocabularies.yaml.

Usage:
    python scripts/validate.py            # validate everything under data/
    python scripts/validate.py --strict    # also fail on warnings

Checks:
    - required fields present and non-empty
    - enum fields (roles, project_type, status, venue_type) draw from
      schema/vocabularies.yaml
    - id matches filename
    - cross-references resolve: project.venue -> venues/, credits[].firm ->
      firms/, firm.successor -> firms/
    - date/year sanity (status_verified is a real date not in the future;
      year_completed/year_expected in a plausible range)
    - project.status == 'announced' requires year_expected, not
      year_completed, and vice versa for completed/in-progress
    - warns (not errors) on: firm with < 1 credited project in this dataset,
      duplicate ids across the three entity types, unsourced records,
      status_verified older than 12 months (due for re-verification),
      operating-reality mismatch (more international-venue credits than
      North America ones, with no recent North America credit — see
      check_operating_reality)

Exit code is non-zero if any error-level finding exists (or, with --strict,
if any warning exists too).
"""
import argparse
import collections
import datetime
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VOCAB_PATH = ROOT / "schema" / "vocabularies.yaml"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# 1800 covers legacy architecture-firm founding dates (e.g. Ayers Saint
# Gross traces to 1912); a project's year_completed will never be this old
# but sharing one bound keeps the check simple.
YEAR_MIN, YEAR_MAX = 1800, datetime.date.today().year + 5
# editorial-policy.md's Activity status staleness rule: a status_verified
# date older than 12 months is due for re-verification, not a fact to trust.
STALENESS_WINDOW_DAYS = 365


class Finding:
    def __init__(self, level, entity, field, message):
        self.level = level  # "error" | "warning"
        self.entity = entity  # e.g. "firms/example-firm.yaml"
        self.field = field
        self.message = message

    def __str__(self):
        tag = "ERROR" if self.level == "error" else "WARN "
        loc = f"{self.entity}" + (f" [{self.field}]" if self.field else "")
        return f"{tag}  {loc}: {self.message}"


def load_vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {
        "roles": {e["id"] for e in raw.get("roles", [])},
        "project_types": {e["id"] for e in raw.get("project_types", [])},
        "firm_statuses": {e["id"] for e in raw.get("firm_statuses", [])},
        "venue_types": {e["id"] for e in raw.get("venue_types", [])},
        "technology_tags": {e["id"] for e in raw.get("technology_tags", [])},
        "platforms": {e["id"] for e in raw.get("platforms", [])},
    }


def load_records(subdir):
    """Return {id: (record_dict, path)} for every non-template yaml in data/<subdir>/."""
    records = {}
    findings = []
    folder = DATA / subdir
    if not folder.is_dir():
        return records, findings
    for path in sorted(folder.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            with open(path, encoding="utf-8") as f:
                record = yaml.safe_load(f)
        except yaml.YAMLError as e:
            findings.append(Finding("error", rel, None, f"invalid YAML: {e}"))
            continue
        if not isinstance(record, dict):
            findings.append(Finding("error", rel, None, "record is not a YAML mapping"))
            continue
        rec_id = record.get("id")
        if not rec_id:
            findings.append(Finding("error", rel, "id", "missing id field"))
            continue
        if rec_id != path.stem:
            findings.append(
                Finding("error", rel, "id", f"id '{rec_id}' does not match filename '{path.stem}'")
            )
        if not SLUG_RE.match(str(rec_id)):
            findings.append(Finding("error", rel, "id", f"'{rec_id}' is not a lowercase kebab-case slug"))
        if rec_id in records:
            findings.append(Finding("error", rel, "id", f"duplicate id '{rec_id}' within {subdir}/"))
        records[rec_id] = (record, rel)
    return records, findings


def require(record, rel, field, findings, *, allow_empty=False):
    val = record.get(field)
    missing = val is None or (not allow_empty and val == "")
    if missing:
        findings.append(Finding("error", rel, field, "required field missing or empty"))
    return val


def check_url(val, rel, field, findings):
    if val and not re.match(r"^https?://", str(val)):
        findings.append(Finding("warning", rel, field, f"'{val}' does not look like a URL"))


def check_place(rec, rel, field, findings):
    """Validate an hq/location mapping. city always required; state required
    for US places (country absent or 'US'), optional otherwise (non-US places
    use country instead — e.g. {city: Amsterdam, country: NL})."""
    place = rec.get(field)
    if not place or not isinstance(place, dict) or not place.get("city"):
        findings.append(Finding("error", rel, field, f"{field}.city is required"))
        return
    country = str(place.get("country", "US")).upper()
    if country == "US" and not place.get("state"):
        findings.append(Finding("error", rel, field, f"{field}.state is required for US places (or set country for non-US)"))


# Folded YAML scalars silently join wrapped lines; a line broken after a
# hyphen produces artifacts like "12-years-in-the- making" in public text.
ARTIFACT_RE = re.compile(r"[A-Za-z]- [a-z]")


def check_text_artifacts(val, rel, field, findings):
    if val and ARTIFACT_RE.search(str(val)):
        findings.append(Finding("warning", rel, field, "contains 'x- y' pattern — likely a folded-scalar line-wrap artifact; rejoin the hyphenated word"))


def check_year(val, rel, field, findings):
    if val is None:
        return
    try:
        year = int(val)
    except (TypeError, ValueError):
        findings.append(Finding("error", rel, field, f"'{val}' is not a year"))
        return
    if not (YEAR_MIN <= year <= YEAR_MAX):
        findings.append(Finding("error", rel, field, f"{year} is outside plausible range {YEAR_MIN}-{YEAR_MAX}"))


def validate_firms(firms, vocab, findings):
    for fid, (rec, rel) in firms.items():
        require(rec, rel, "name", findings)
        check_place(rec, rel, "hq", findings)
        for office in rec.get("other_offices") or []:
            if not isinstance(office, dict) or not office.get("city"):
                findings.append(Finding("warning", rel, "other_offices", f"malformed entry: {office}"))
        check_year(rec.get("founded"), rel, "founded", findings)
        roles = rec.get("roles") or []
        if not roles:
            findings.append(Finding("error", rel, "roles", "at least one role is required"))
        for r in roles:
            if r not in vocab["roles"]:
                findings.append(Finding("error", rel, "roles", f"'{r}' is not in vocabularies.yaml roles"))
        status = require(rec, rel, "status", findings)
        if status and status not in vocab["firm_statuses"]:
            findings.append(Finding("error", rel, "status", f"'{status}' is not a valid firm_status"))
        require(rec, rel, "status_basis", findings)
        verified = require(rec, rel, "status_verified", findings)
        if verified is not None:
            if isinstance(verified, (datetime.date, datetime.datetime)):
                d = verified if isinstance(verified, datetime.date) else verified.date()
                today = datetime.date.today()
                if d > today:
                    findings.append(Finding("error", rel, "status_verified", f"{d} is in the future"))
                elif (today - d).days > STALENESS_WINDOW_DAYS:
                    findings.append(Finding(
                        "warning", rel, "status_verified",
                        f"{d} is over 12 months old — status is due for re-verification "
                        f"per editorial-policy.md's staleness rule",
                    ))
            else:
                findings.append(Finding("error", rel, "status_verified", f"'{verified}' is not a YAML date (use YYYY-MM-DD unquoted)"))
        successor = rec.get("successor")
        if successor and successor not in firms:
            findings.append(Finding("error", rel, "successor", f"successor firm '{successor}' not found in data/firms/"))
        summary = require(rec, rel, "summary", findings)
        check_text_artifacts(summary, rel, "summary", findings)
        sources = rec.get("sources") or []
        if not sources:
            findings.append(Finding("error", rel, "sources", "at least one source is required"))
        for s in sources:
            check_url(s, rel, "sources", findings)
        check_url(rec.get("website"), rel, "website", findings)


def validate_projects(projects, firms, venues, vocab, findings):
    for pid, (rec, rel) in projects.items():
        require(rec, rel, "name", findings)
        venue = require(rec, rel, "venue", findings)
        if venue and venue not in venues:
            findings.append(Finding("error", rel, "venue", f"venue '{venue}' not found in data/venues/"))
        ptype = require(rec, rel, "project_type", findings)
        if ptype and ptype not in vocab["project_types"]:
            findings.append(Finding("error", rel, "project_type", f"'{ptype}' is not a valid project_type"))
        status = rec.get("status", "completed")
        if status not in {"completed", "announced", "in-progress"}:
            findings.append(Finding("error", rel, "status", f"'{status}' is not completed|announced|in-progress"))
        year_completed = rec.get("year_completed")
        year_expected = rec.get("year_expected")
        if status == "announced":
            if not year_expected:
                findings.append(Finding("error", rel, "year_expected", "required when status is 'announced'"))
            check_year(year_expected, rel, "year_expected", findings)
            if year_completed:
                findings.append(Finding("warning", rel, "year_completed", "set alongside status 'announced'; expected year_expected instead"))
        else:
            if not year_completed:
                findings.append(Finding("error", rel, "year_completed", "required unless status is 'announced'"))
            check_year(year_completed, rel, "year_completed", findings)
        credits = rec.get("credits") or []
        if not credits:
            findings.append(Finding("error", rel, "credits", "at least one credit is required"))
        for c in credits:
            if not isinstance(c, dict):
                findings.append(Finding("error", rel, "credits", f"malformed credit entry: {c}"))
                continue
            cfirm = c.get("firm")
            crole = c.get("role")
            if not cfirm:
                findings.append(Finding("error", rel, "credits", "credit missing 'firm'"))
            elif cfirm not in firms:
                findings.append(Finding("warning", rel, "credits", f"credited firm '{cfirm}' has no record in data/firms/ yet (allowed temporarily)"))
            if not crole:
                findings.append(Finding("error", rel, "credits", "credit missing 'role'"))
            elif crole not in vocab["roles"]:
                findings.append(Finding("error", rel, "credits", f"'{crole}' is not in vocabularies.yaml roles"))
        for t in rec.get("technology_tags") or []:
            if t not in vocab["technology_tags"]:
                findings.append(Finding("error", rel, "technology_tags", f"'{t}' is not in vocabularies.yaml technology_tags"))
        for pl in rec.get("platforms") or []:
            if pl not in vocab["platforms"]:
                findings.append(Finding("error", rel, "platforms", f"'{pl}' is not in vocabularies.yaml platforms"))
        for award in rec.get("recognition") or []:
            if not isinstance(award, dict) or not award.get("award") or not award.get("year") or not award.get("source"):
                findings.append(Finding("error", rel, "recognition", f"each recognition entry needs award, year, source: {award}"))
                continue
            check_year(award.get("year"), rel, "recognition.year", findings)
            check_url(award.get("source"), rel, "recognition.source", findings)
        summary = require(rec, rel, "summary", findings)
        check_text_artifacts(summary, rel, "summary", findings)
        check_text_artifacts(rec.get("description"), rel, "description", findings)
        sources = rec.get("sources") or []
        if not sources:
            findings.append(Finding("error", rel, "sources", "at least one source is required"))
        for s in sources:
            check_url(s, rel, "sources", findings)


def validate_venues(venues, vocab, findings):
    for vid, (rec, rel) in venues.items():
        require(rec, rel, "name", findings)
        vtype = require(rec, rel, "venue_type", findings)
        if vtype and vtype not in vocab["venue_types"]:
            findings.append(Finding("error", rel, "venue_type", f"'{vtype}' is not a valid venue_type"))
        check_place(rec, rel, "location", findings)
        att = rec.get("annual_attendance")
        if att is not None:
            if not isinstance(att, dict) or not att.get("figure") or not att.get("year") or not att.get("source"):
                findings.append(Finding("error", rel, "annual_attendance", "needs figure, year, and source (a published figure — never an estimate)"))
            else:
                if not isinstance(att.get("figure"), int) or att["figure"] <= 0:
                    findings.append(Finding("error", rel, "annual_attendance", f"figure '{att.get('figure')}' must be a positive integer"))
                check_year(att.get("year"), rel, "annual_attendance.year", findings)
                check_url(att.get("source"), rel, "annual_attendance.source", findings)
        check_url(rec.get("website"), rel, "website", findings)


def cross_dataset_id_collisions(firms, projects, venues, findings):
    seen = {}
    for kind, records in (("firms", firms), ("projects", projects), ("venues", venues)):
        for rid in records:
            if rid in seen:
                findings.append(
                    Finding("warning", f"{kind}/{rid}.yaml", "id", f"id '{rid}' also used in {seen[rid]}/ — ids should be globally unique for clean URLs")
                )
            else:
                seen[rid] = kind


def firm_project_coverage(firms, projects, findings):
    credited = set()
    for _, (rec, _) in projects.items():
        for c in rec.get("credits") or []:
            if isinstance(c, dict) and c.get("firm"):
                credited.add(c["firm"])
    for fid, (_, rel) in firms.items():
        if fid not in credited:
            findings.append(Finding("warning", rel, None, "firm has no credited project in this dataset yet"))


# A firm's status_verified/hq claims North America operating reality, but
# the credit record itself can quietly disagree (Tellart, 2026-07-19: a
# Providence-incorporated firm record whose actual work was overwhelmingly
# recent and international — legal registration isn't the bar,
# editorial-policy.md's "operating reality governs" is). This check catches
# the shape of that mismatch mechanically so it doesn't require someone to
# remember to look.
GAP_YEARS_THRESHOLD = 4


def check_operating_reality(firms, projects, venues, findings):
    venue_country = {}
    for vid, (rec, _) in venues.items():
        loc = rec.get("location") or {}
        venue_country[vid] = str(loc.get("country", "US")).upper()

    na_years = collections.defaultdict(list)
    intl_years = collections.defaultdict(list)
    for _, (rec, _) in projects.items():
        year = rec.get("year_completed") or rec.get("year_expected")
        if not year:
            continue
        country = venue_country.get(rec.get("venue"), "US")
        for c in rec.get("credits") or []:
            if not isinstance(c, dict) or not c.get("firm"):
                continue
            fid = c["firm"]
            (na_years if country in ("US", "CA") else intl_years)[fid].append(year)

    for fid, (_, rel) in firms.items():
        intl = intl_years.get(fid) or []
        if not intl:
            continue
        na = na_years.get(fid) or []
        max_intl, max_na = max(intl), (max(na) if na else None)
        gap = (max_intl - max_na) if max_na is not None else None
        imbalanced = len(intl) > len(na)
        stale_or_absent = max_na is None or gap >= GAP_YEARS_THRESHOLD
        if imbalanced and stale_or_absent:
            detail = (
                f"no North America-venue credits" if max_na is None
                else f"most recent North America-venue credit is {gap} year(s) "
                     f"older than the most recent international one ({max_na} vs. {max_intl})"
            )
            findings.append(Finding(
                "warning", rel, "hq",
                f"possible operating-reality mismatch — {len(intl)} international-venue "
                f"credit(s) vs. {len(na)} North America-venue credit(s), and {detail}; "
                f"re-check per editorial-policy.md's operating-reality rule before trusting "
                f"this firm record as-is",
            ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    args = parser.parse_args()

    vocab = load_vocab()
    findings = []

    firms, f1 = load_records("firms")
    projects, f2 = load_records("projects")
    venues, f3 = load_records("venues")
    findings += f1 + f2 + f3

    validate_firms(firms, vocab, findings)
    validate_projects(projects, firms, venues, vocab, findings)
    validate_venues(venues, vocab, findings)
    cross_dataset_id_collisions(firms, projects, venues, findings)
    firm_project_coverage(firms, projects, findings)
    check_operating_reality(firms, projects, venues, findings)

    findings.sort(key=lambda f: (f.level != "error", f.entity, f.field or ""))

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    for f in findings:
        print(f)

    print()
    print(f"{len(firms)} firms, {len(projects)} projects, {len(venues)} venues checked.")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s).")

    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
