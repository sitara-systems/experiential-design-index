#!/usr/bin/env python3
"""Build the static site for The Experiential Design Index from data/*.yaml.

Usage:
    python scripts/build_site.py

Reads every non-template YAML record in data/{firms,projects,venues}/,
derives cross-references (a firm's projects, a venue's projects) by
scanning project credits/venue fields (never stored redundantly on the
firm/venue record, per schema/schema.md), and renders a plain
Wikipedia/IMDb-style static site into _site/ using Jinja2 templates from
templates/. Also emits robots.txt, llms.txt, sitemap.xml, and open-data
exports (JSON + CSV) under _site/data/.

Stdlib + PyYAML + Jinja2 only, following scripts/validate.py's conventions
(same id-derivation, same YAML loading approach). This script never reads
or writes anything under data/, schema/, or docs/ — read-only on data/,
additive everywhere else.
"""
import argparse
import csv
import datetime
import json
import os
import pathlib
import re
import shutil
import sys
import urllib.parse

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
SITE = ROOT / "_site"
VOCAB_PATH = ROOT / "schema" / "vocabularies.yaml"

SITE_NAME = "The Experiential Design Index"
# SITE_URL overridable via env for non-production deploys (e.g. an interim
# GitHub Pages preview at a different host/path); defaults to the D1 target.
SITE_URL = os.environ.get("SITE_URL", "https://sitara.systems/experiential-design-index")
# Set NOINDEX=1 for preview deploys not meant to be crawled/cited -- emits a
# blanket-disallow robots.txt and a noindex meta tag on every page, so an
# interim URL never competes with the eventual production launch.
NOINDEX = os.environ.get("NOINDEX") == "1"

# Directory-display threshold (docs/editorial-policy.md, decided 2026-07-19).
# Distinct from the 3-project dataset-inclusion bar enforced by validate.py:
# a firm below this count still gets a full record -- its own page, every
# project-page credit link, and the open-data export -- it just isn't
# surfaced in the browse/list index or that index's JSON-LD ItemList.
DIRECTORY_DISPLAY_MIN_PROJECTS = 8

# Dataset-inclusion bar (validate.py enforces this on the data itself; this
# constant exists only so the About page can state the number from one
# place instead of a second hardcoded copy going stale).
DATASET_INCLUSION_MIN_PROJECTS = 3
# Internal-link prefix derived from SITE_URL's path so links resolve at the
# deployed location. SITE_URL is the single knob: change it at deploy time and
# both absolute URLs (sitemap/JSON-LD) and internal hrefs follow.
BASE = urllib.parse.urlsplit(SITE_URL).path.rstrip("/")

# Internal bookkeeping phrases that must not render on public pages: whole
# parentheticals mentioning record/vocab gaps, plus the bare phrase.
_NOTE_PAREN_INTERNAL_RE = re.compile(
    r"\s*\([^)]*(?:no firm records? yet|not covered by (?:the )?current vocabulary)[^)]*\)",
    re.IGNORECASE,
)
_NOTE_BARE_INTERNAL_RE = re.compile(r"\s*[;,]?\s*no firm records? yet\s*", re.IGNORECASE)


def public_note(note):
    """Strip editor-facing bookkeeping from a credit note for public display."""
    if not note:
        return None
    cleaned = _NOTE_PAREN_INTERNAL_RE.sub("", note)
    cleaned = _NOTE_BARE_INTERNAL_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ;,")
    return cleaned or None


# ---------------------------------------------------------------- loading --

def load_vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {
        "roles": {e["id"]: e["label"] for e in raw.get("roles", [])},
        "project_types": {e["id"]: e["label"] for e in raw.get("project_types", [])},
        "firm_statuses": {e["id"]: e["label"] for e in raw.get("firm_statuses", [])},
        "venue_types": {e["id"]: e["label"] for e in raw.get("venue_types", [])},
        "technology_tags": {e["id"]: e["label"] for e in raw.get("technology_tags", [])},
    }


def load_records(subdir):
    """Return {id: record_dict} for every non-template yaml in data/<subdir>/.
    Mirrors scripts/validate.py's load_records id-derivation (id == filename stem)."""
    records = {}
    folder = DATA / subdir
    for path in sorted(folder.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            record = yaml.safe_load(f)
        if not isinstance(record, dict) or not record.get("id"):
            continue  # malformed records are validate.py's job to catch, not build's
        records[record["id"]] = record
    return records


# -------------------------------------------------------------- derivation --

def year_display(rec):
    if rec.get("status") == "announced":
        return f"{rec.get('year_expected', '?')} (announced)"
    if rec.get("status") == "in-progress":
        return f"{rec.get('year_completed') or rec.get('year_expected', '?')} (in progress)"
    return str(rec.get("year_completed", "?"))


def year_label(rec):
    return "Year expected" if rec.get("status") == "announced" else "Year completed"


def enrich_projects(projects, firms, venues, vocab, warnings):
    """Attach display-ready derived fields to each project in place."""
    for pid, p in projects.items():
        venue_id = p.get("venue")
        venue = venues.get(venue_id)
        p["venue_exists"] = venue is not None
        p["venue_name"] = venue["name"] if venue else (venue_id or "(unknown venue)")
        p["project_type_label"] = vocab["project_types"].get(p.get("project_type"), p.get("project_type") or "")
        p["status_label"] = {
            "completed": "Completed",
            "announced": "Announced",
            "in-progress": "In progress",
        }.get(p.get("status", "completed"), (p.get("status") or "completed").title())
        p["year_display"] = year_display(p)
        p["year_label"] = year_label(p)
        credits = p.get("credits") or []
        role_labels = []
        for c in credits:
            if not isinstance(c, dict):
                continue
            firm_id = c.get("firm")
            firm = firms.get(firm_id)
            c["firm_exists"] = firm is not None
            c["firm_name"] = firm["name"] if firm else (firm_id or "(unknown firm)")
            c["role_label"] = vocab["roles"].get(c.get("role"), c.get("role") or "")
            # Credit-level technology attribution renders as a marker on the
            # credits table -- readers (and the corrections process) can see
            # which credit delivered a tagged technology.
            c["technology_tag_labels"] = [vocab["technology_tags"].get(t, t)
                                          for t in (c.get("technology_tags") or [])]
            # Editor-facing bookkeeping ("no firm record yet") never renders
            # publicly — pages and open-data exports both get the cleaned note.
            c["note"] = public_note(c.get("note"))
            if not firm:
                warnings.append(f"project '{pid}': credited firm '{firm_id}' has no firm record (rendered unlinked)")
            else:
                role_labels.append(c["role_label"])
        p["role_labels"] = role_labels or [vocab["roles"].get(c.get("role"), "") for c in credits if isinstance(c, dict)]


def enrich_firms(firms, projects, vocab):
    """Attach display-ready derived fields, incl. the derived project list."""
    by_firm = {fid: [] for fid in firms}
    for pid, p in projects.items():
        for c in p.get("credits") or []:
            if isinstance(c, dict) and c.get("firm") in by_firm:
                by_firm[c["firm"]].append((pid, p, c))

    for fid, f in firms.items():
        f["role_labels"] = [vocab["roles"].get(r, r) for r in (f.get("roles") or [])]
        f["status_label"] = vocab["firm_statuses"].get(f.get("status"), f.get("status") or "")
        successor = f.get("successor")
        f["successor_name"] = firms[successor]["name"] if successor and successor in firms else successor

        entries = sorted(by_firm.get(fid, []), key=lambda t: (t[1].get("year_completed") or t[1].get("year_expected") or 0), reverse=True)
        # One row per DISTINCT project — a firm holding several credits on
        # the same project (design + fabrication + media) gets one entry
        # with the roles merged, not one per credit. The project count (firm
        # page header, directory threshold) counts projects, not credits.
        proj_map = {}
        for pid, p, c in entries:
            e = proj_map.get(pid)
            if e is None:
                proj_map[pid] = e = {
                    "id": pid,
                    "name": p["name"],
                    "venue": p.get("venue"),
                    "venue_exists": p.get("venue_exists"),
                    "venue_name": p.get("venue_name"),
                    "role_labels": [],
                    "year_display": p.get("year_display"),
                }
            label = c.get("role_label", "")
            if label and label not in e["role_labels"]:
                e["role_labels"].append(label)
        f["projects"] = list(proj_map.values())


def enrich_venues(venues, projects, vocab):
    by_venue = {vid: [] for vid in venues}
    for pid, p in projects.items():
        vid = p.get("venue")
        if vid in by_venue:
            by_venue[vid].append((pid, p))

    for vid, v in venues.items():
        v["venue_type_label"] = vocab["venue_types"].get(v.get("venue_type"), v.get("venue_type") or "")
        entries = sorted(by_venue.get(vid, []), key=lambda t: (t[1].get("year_completed") or t[1].get("year_expected") or 0), reverse=True)
        proj_list = []
        for pid, p in entries:
            proj_list.append({
                "id": pid,
                "name": p["name"],
                "project_type_label": p.get("project_type_label"),
                "year_display": p.get("year_display"),
            })
        v["projects"] = proj_list
        v["project_count"] = len(proj_list)


# --------------------------------------------------------- ranked lists ----
# HANDOFF track F: published 2026-07-19 (Nathan: publish all data-ready
# families). Scoring formula is docs/editorial-policy.md's "Ranked lists"
# section, verbatim -- do not hand-tune weights here; edit the policy doc
# first, then mirror the change. Families still gated on missing data
# (most-awarded institutions, platform lists, small-studios,
# woman-/minority-owned) simply aren't built yet -- see the list below.

RANKED_LIST_MIN_FIRMS = 8
RANKED_LIST_WINDOW_YEARS = 5
RECENCY_WEIGHTS = {0: 1.0, 1: 1.0, 2: 0.75, 3: 0.75, 4: 0.5, 5: 0.5}
SOURCING_BONUS_PER_PROJECT = 0.1
SOURCING_BONUS_CAP = 0.5
# Display rules (editorial-policy.md §Ranked lists, amended 2026-07-19):
# a numbered rank requires >= 2 counted items (one project is not a track
# record); the ranked table shows at most the top 10; every other firm with
# eligible activity stays on the page in an unranked alphabetical section.
# The 8-firm minimum depth counts rank-eligible firms only.
RANKED_LIST_TOP_N = 10
RANKED_LIST_MIN_ITEMS_TO_RANK = 2


def split_rows(rows):
    """Apply the display rules to a family's scored rows.

    Returns (ranked, top_rows, also_rows): ranked=False means the family
    publishes as an unranked roundup (all rows alphabetical in top_rows,
    also_rows empty)."""
    rank_eligible = [r for r in rows
                     if len(r["eligible_projects"]) >= RANKED_LIST_MIN_ITEMS_TO_RANK]
    if len(rank_eligible) < RANKED_LIST_MIN_FIRMS:
        return False, sorted(rows, key=lambda r: r["firm"]["name"].lower()), []
    top = rank_eligible[:RANKED_LIST_TOP_N]
    top_ids = {r["firm"]["id"] for r in top}
    also = sorted((r for r in rows if r["firm"]["id"] not in top_ids),
                  key=lambda r: r["firm"]["name"].lower())
    return True, top, also


def _eligible_projects_for(projects, current_year):
    """Projects eligible for any ranked-list scoring: completed, dated,
    within the trailing window. Returns [(pid, p, age)]."""
    out = []
    for pid, p in projects.items():
        if (p.get("status") or "completed") != "completed":
            continue
        year = p.get("year_completed")
        if not year:
            continue
        age = current_year - year
        if 0 <= age <= RANKED_LIST_WINDOW_YEARS:
            out.append((pid, p, age))
    return out


def _independent_sourcing_bonus(p, firm_website):
    """+0.1 if the project has 2+ distinct source domains not operated by
    the credited firm (its own site doesn't count toward corroboration)."""
    firm_domain = urllib.parse.urlsplit(firm_website).netloc if firm_website else None
    domains = {urllib.parse.urlsplit(s).netloc for s in (p.get("sources") or []) if s}
    independent = domains - ({firm_domain} if firm_domain else set())
    return SOURCING_BONUS_PER_PROJECT if len(independent) >= 2 else 0.0


def score_firms(firms, projects, eligible, credit_matches):
    """Score every screened firm for one list family.

    credit_matches(project, credit) -> bool decides whether a credit counts
    toward this family (e.g. credit['role'] == 'exhibit-design', or the
    project carries a given technology_tag regardless of role).

    Returns rows sorted by (score desc, status_verified desc, name asc):
    [{"firm": firm_dict, "score": float, "eligible_projects": [...]}]

    Inactive firms never appear on ranked lists or count toward minimum
    depth (editorial ruling 2026-07-20) -- a list answering "who can I
    hire" can't include firms that no longer exist. Their records, project
    credits, and directory presence are unaffected.
    """
    rows = []
    for fid, f in firms.items():
        if f.get("status") == "inactive":
            continue
        score = 0.0
        bonus = 0.0
        eligible_projects = []
        for pid, p, age in eligible:
            credits = p.get("credits") or []
            matched = [c for c in credits if isinstance(c, dict) and c.get("firm") == fid and credit_matches(p, c)]
            if not matched:
                continue
            score += RECENCY_WEIGHTS[age]
            bonus += _independent_sourcing_bonus(p, f.get("website"))
            eligible_projects.append({
                "id": pid, "name": p["name"],
                "year": p.get("year_completed"),
            })
        if not eligible_projects:
            continue
        score += min(bonus, SOURCING_BONUS_CAP)
        eligible_projects.sort(key=lambda ep: ep["year"] or 0, reverse=True)
        rows.append({"firm": f, "score": score, "eligible_projects": eligible_projects})

    _sort_rows(rows)
    return rows


def _sort_rows(rows):
    # Three ascending stable sorts, least- to most-significant key, so the
    # tie-break rule (score desc, then most-recent status_verified, then
    # name as a final deterministic tiebreak) stays legible.
    rows.sort(key=lambda r: r["firm"]["name"].lower())
    rows.sort(key=lambda r: r["firm"].get("status_verified") or datetime.date.min, reverse=True)
    rows.sort(key=lambda r: r["score"], reverse=True)


def role_holders(firms, role_id):
    # Role-identity rule (editorial-policy.md, 2026-07-19): a firm appears
    # on a role's list only if its own record declares that role as an
    # engageable standalone service. Project credits in other roles stay on
    # project pages but don't place the firm on that role's list.
    return {fid: f for fid, f in firms.items() if role_id in (f.get("roles") or [])}


def build_role_list(role_id, role_label, firms, projects, current_year):
    eligible = _eligible_projects_for(projects, current_year)
    rows = score_firms(role_holders(firms, role_id), projects, eligible,
                       lambda p, c: c.get("role") == role_id)
    ranked, top, also = split_rows(rows)
    return {
        "slug": f"role-{role_id}",
        "title": (f"Top {len(top)} {role_label} Firms" if ranked
                  else f"Firms Working In {role_label}"),
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
    }


def build_tech_tag_list(tag_id, tag_label, firms, projects, current_year):
    eligible = _eligible_projects_for(projects, current_year)
    # Credit-level attribution (2026-07-19): only the credit(s) that actually
    # delivered the tagged technology carry it (credit-level technology_tags,
    # set from sourced evidence). Being credited on a tagged project in
    # another capacity -- AV install, fabrication, lighting, the surrounding
    # gallery -- does not place a firm on the technology list.
    rows = score_firms(firms, projects, eligible,
                       lambda p, c: tag_id in (c.get("technology_tags") or []))
    ranked, top, also = split_rows(rows)
    return {
        "slug": f"tech-{tag_id}",
        "title": (f"Top {len(top)} {tag_label}-Credited Firms" if ranked
                  else f"Firms With {tag_label}-Credited Projects"),
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "methodology_note": ("Counts only credits attributed with the "
                             f"{tag_label} technology tag -- the firm(s) that "
                             "delivered the tagged technology on each project, "
                             "per the project's cited sources. Other firms "
                             "credited on the same projects (AV integration, "
                             "fabrication, lighting, exhibit design around the "
                             "installation) do not count. Standard recency "
                             "weighting and sourcing bonus apply."),
    }


# Cross-role list families (venue-type, most-awarded, largest-reach,
# most-active) count design-discipline credits only, held in a role the firm
# offers standalone (editorial rulings 2026-07-19/20): the founding principle
# is "never a cross-role master ranking" — an AV integrator and an exhibit
# designer with the same count are not answers to the same buyer question.
# Per-role lists remain the home for execution/systems disciplines.
DESIGN_LIST_ROLES = {
    "exhibit-design", "interpretive-planning", "media-design", "architecture",
    "master-planning", "landscape-architecture", "graphics-wayfinding",
    "lighting-design",
}


def design_identity_credit(firms, p, c):
    """Membership test for cross-role list families: a design-discipline
    credit held in a role the firm offers standalone (its record roles)."""
    return (c.get("role") in DESIGN_LIST_ROLES
            and c.get("role") in ((firms.get(c.get("firm")) or {}).get("roles") or []))


def build_venue_type_list(vt_id, vt_label, firms, projects, venues, current_year):
    # Venue-type specialization ("who does natural history museums") -- the
    # standard formula, filtered by the venue's type instead of the credit's
    # role. Counts only design-discipline credits held in a role the firm
    # offers standalone (its record roles) -- fabrication/AV/consulting
    # credits, and credits in accreted non-identity roles, don't count.
    eligible = _eligible_projects_for(projects, current_year)
    rows = score_firms(firms, projects, eligible,
                       lambda p, c: ((venues.get(p.get("venue")) or {}).get("venue_type") == vt_id
                                     and design_identity_credit(firms, p, c)))
    ranked, top, also = split_rows(rows)
    return {
        "slug": f"venue-type-{vt_id}",
        "title": (f"Top {len(top)} Firms for {vt_label} Projects" if ranked
                  else f"Firms With {vt_label} Projects"),
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "ranking_basis": (f"Ranked by recency-weighted eligible project count at "
                          f"{vt_label.lower()} venues, {current_year - RANKED_LIST_WINDOW_YEARS}"
                          f"–{current_year}"),
        "methodology_note": ("Counts design-discipline credits only -- exhibit "
                             "design, interpretive planning, media design, "
                             "architecture, master planning, landscape "
                             "architecture, environmental graphics, lighting "
                             "design -- held in a role the firm offers as a "
                             "standalone service. Fabrication, AV integration, "
                             "and consulting credits appear on project pages "
                             "but don't place a firm on this list. Standard "
                             "recency weighting and sourcing bonus apply."),
    }


def build_awards_list(firms, projects, current_year):
    # Most-awarded firms: counts `recognition` entries (juried programs only,
    # enforced at data entry) with award year in the trailing window, on
    # completed projects credited to the firm. Simple count, not the
    # recency-weighted formula -- an award year is already a recency signal.
    rows = []
    for fid, f in firms.items():
        if f.get("status") == "inactive":
            continue
        total = 0
        items = []
        for pid, p in projects.items():
            if (p.get("status") or "completed") != "completed":
                continue
            recs = [r for r in (p.get("recognition") or [])
                    if isinstance(r, dict) and isinstance(r.get("year"), int)
                    and 0 <= current_year - r["year"] <= RANKED_LIST_WINDOW_YEARS]
            if not recs:
                continue
            if not any(isinstance(c, dict) and c.get("firm") == fid
                       and design_identity_credit(firms, p, c)
                       for c in (p.get("credits") or [])):
                continue
            total += len(recs)
            items.append({"id": pid, "name": p["name"], "year": p.get("year_completed")})
        if total:
            items.sort(key=lambda ep: ep["year"] or 0, reverse=True)
            rows.append({"firm": f, "score": total, "score_display": str(total),
                         "eligible_projects": items})
    _sort_rows(rows)
    ranked, top, also = split_rows(rows)
    return {
        "slug": "most-awarded-firms",
        "title": "Most-Awarded Firms" if ranked else "Firms With Juried Award Recognition",
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "ranking_basis": (f"Ranked by juried award recognitions, award years "
                          f"{current_year - RANKED_LIST_WINDOW_YEARS}–{current_year}"),
        "score_label": "Awards",
        "items_label": "Recognized projects",
        "methodology_note": ("Counts recognition entries from juried award programs "
                             "(no pay-to-enter schemes) with an award year in the "
                             "trailing 5 years, on completed projects where the firm "
                             "holds a design-discipline credit in a role it offers "
                             "standalone. Execution and systems credits (fabrication, "
                             "AV integration, consulting) don't count a recognition. "
                             "Ties broken by most recent status-verification date."),
    }


def build_reach_list(firms, projects, venues, current_year):
    # Largest reach: combined published annual visitorship of the distinct
    # venues hosting a firm's trailing-window work. Published figures only,
    # never estimated -- venues without a published figure contribute zero.
    eligible = _eligible_projects_for(projects, current_year)
    rows = []
    for fid, f in firms.items():
        if f.get("status") == "inactive":
            continue
        vset = {}
        for pid, p, age in eligible:
            if not any(isinstance(c, dict) and c.get("firm") == fid
                       and design_identity_credit(firms, p, c)
                       for c in (p.get("credits") or [])):
                continue
            v = venues.get(p.get("venue"))
            a = (v or {}).get("annual_attendance")
            if isinstance(a, dict) and a.get("figure"):
                vset[v["id"]] = v
        if not vset:
            continue
        total = sum(v["annual_attendance"]["figure"] for v in vset.values())
        items = [{"id": vid, "name": v["name"], "kind": "venue",
                  "label": f"{v['annual_attendance']['figure']:,}/yr"}
                 for vid, v in sorted(vset.items(), key=lambda kv: kv[1]["name"].lower())]
        rows.append({"firm": f, "score": total, "score_display": f"{total:,}",
                     "eligible_projects": items})
    _sort_rows(rows)
    ranked, top, also = split_rows(rows)
    return {
        "slug": "largest-reach",
        "title": "Largest Reach: Combined Venue Visitorship" if ranked else "Firms by Venue Visitorship",
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "ranking_basis": (f"Ranked by combined published annual attendance of distinct "
                          f"venues hosting the firm's {current_year - RANKED_LIST_WINDOW_YEARS}"
                          f"–{current_year} work"),
        "score_label": "Combined visitors/yr",
        "items_label": "Counted venues",
        "methodology_note": ("Sums each venue's published annual attendance figure once "
                             "per firm (distinct venues, not per project), over venues "
                             "hosting the firm's completed trailing-5-year work where "
                             "the firm holds a design-discipline credit in a role it "
                             "offers standalone. Published figures only -- venues "
                             "without a published figure count zero, and figures come "
                             "from different reporting years. Ties broken by most "
                             "recent status-verification date."),
    }


def build_annual_list(firms, projects, list_year):
    # Annual most-active: completed projects recorded in the index for one
    # calendar year. The annual-franchise anchor; carries an honesty clause
    # about index coverage rather than pretending to census the industry.
    rows = []
    for fid, f in firms.items():
        if f.get("status") == "inactive":
            continue
        items = []
        for pid, p in projects.items():
            if (p.get("status") or "completed") != "completed":
                continue
            if p.get("year_completed") != list_year:
                continue
            if any(isinstance(c, dict) and c.get("firm") == fid
                   and design_identity_credit(firms, p, c)
                   for c in (p.get("credits") or [])):
                items.append({"id": pid, "name": p["name"], "year": list_year})
        if items:
            items.sort(key=lambda ep: ep["name"].lower())
            rows.append({"firm": f, "score": len(items), "score_display": str(len(items)),
                         "eligible_projects": items})
    _sort_rows(rows)
    ranked, top, also = split_rows(rows)
    return {
        "slug": f"most-active-{list_year}",
        "title": f"Most Active Firms, {list_year}",
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "ranking_basis": f"Ranked by completed projects recorded in the index for {list_year}",
        "score_label": "Projects",
        "items_label": f"{list_year} projects",
        "methodology_note": (f"Counts completed projects with year_completed = {list_year} "
                             "where the firm holds a design-discipline credit in a role "
                             "it offers standalone (fabrication, AV integration, and "
                             "consulting credits don't count). Ties broken by most "
                             "recent status-verification date."),
    }


# US Census Bureau regions (a published external standard, not an editorial
# invention) + Canada as its own region. Firms are assigned by hq.
US_CENSUS_REGIONS = {
    "Northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "Midwest": {"IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"},
    "South": {"DE", "FL", "GA", "MD", "NC", "SC", "VA", "DC", "WV",
              "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"},
    "West": {"AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"},
}
REGION_NAMES = ["Northeast", "Midwest", "South", "West", "Canada"]


def firm_region(f):
    hq = f.get("hq") or {}
    if hq.get("country") == "CA" or (hq.get("province") and not hq.get("state")):
        return "Canada"
    st = hq.get("state")
    for name, states in US_CENSUS_REGIONS.items():
        if st in states:
            return name
    return None


def build_role_region_list(role_id, role_label, region, firms, projects, current_year):
    region_display = region if region == "Canada" else f"{region} US"
    regional = {fid: f for fid, f in role_holders(firms, role_id).items()
                if firm_region(f) == region}
    eligible = _eligible_projects_for(projects, current_year)
    rows = score_firms(regional, projects, eligible, lambda p, c: c.get("role") == role_id)
    ranked, top, also = split_rows(rows)
    return {
        "slug": f"role-{role_id}-region-{region.lower()}",
        "title": (f"Top {len(top)} {role_label} Firms: {region_display}" if ranked
                  else f"{role_label} Firms: {region_display}"),
        "ranked": ranked,
        "rows": top,
        "also_rows": also,
        "ranking_basis": (f"Ranked by recency-weighted eligible project count, "
                          f"{current_year - RANKED_LIST_WINDOW_YEARS}–{current_year}, "
                          f"firms headquartered in the {region_display} "
                          f"(US Census Bureau regions; Canada listed separately)"),
    }


# ------------------------------------------------------------------ JSON-LD --

def breadcrumb_ld(crumbs):
    """crumbs: list of (name, url) tuples, url may be None for the current page."""
    items = []
    for i, (name, url) in enumerate(crumbs, start=1):
        item = {"@type": "ListItem", "position": i, "name": name}
        if url:
            item["item"] = url
        items.append(item)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def firm_jsonld(f, url):
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": f["name"],
        "url": url,
    }
    if f.get("website"):
        org["sameAs"] = [f["website"]]
    if f.get("founded"):
        org["foundingDate"] = str(f["founded"])
    if f.get("hq"):
        org["address"] = {
            "@type": "PostalAddress",
            "addressLocality": f["hq"].get("city"),
            "addressRegion": f["hq"].get("state"),
            "addressCountry": f["hq"].get("country", "US"),
        }
    return [org, breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Firms", f"{SITE_URL}/firms/index.html"), (f["name"], None)])]


def project_jsonld(p, url):
    creators = []
    for c in p.get("credits") or []:
        if isinstance(c, dict):
            creators.append({"@type": "Organization", "name": c.get("firm_name")})
    work = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": p["name"],
        "description": p.get("summary"),
        "dateCreated": str(p.get("year_completed") or p.get("year_expected") or ""),
    }
    if creators:
        work["creator"] = creators
    return [work, breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Projects", f"{SITE_URL}/projects/index.html"), (p["name"], None)])]


def venue_jsonld(v, url):
    place = {
        "@context": "https://schema.org",
        "@type": "Place",
        "name": v["name"],
        "url": url,
    }
    if v.get("location"):
        place["address"] = {
            "@type": "PostalAddress",
            "addressLocality": v["location"].get("city"),
            "addressRegion": v["location"].get("state"),
            "addressCountry": v["location"].get("country", "US"),
        }
    return [place, breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Venues", f"{SITE_URL}/venues/index.html"), (v["name"], None)])]


def list_jsonld(name, url, item_urls):
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "itemListElement": [
            {"@type": "ListItem", "position": i, "url": u} for i, u in enumerate(item_urls, start=1)
        ],
    }


def dumps_ld(obj):
    if isinstance(obj, list):
        return json.dumps(obj, indent=2, ensure_ascii=False)
    return json.dumps(obj, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------- build --

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "firms").mkdir(parents=True)
    (SITE / "projects").mkdir(parents=True)
    (SITE / "venues").mkdir(parents=True)
    (SITE / "data").mkdir(parents=True)
    (SITE / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "assets" / "filter.js", SITE / "assets" / "filter.js")

    vocab = load_vocab()
    firms = load_records("firms")
    projects = load_records("projects")
    venues = load_records("venues")

    warnings = []
    enrich_projects(projects, firms, venues, vocab, warnings)
    enrich_firms(firms, projects, vocab)
    enrich_venues(venues, projects, vocab)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def render(template_name, out_path, **ctx):
        tmpl = env.get_template(template_name)
        html = tmpl.render(base=BASE, noindex=NOINDEX, **ctx)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")

    firms_sorted = sorted(firms.values(), key=lambda f: f["name"].lower())
    projects_sorted = sorted(projects.values(), key=lambda p: p["name"].lower())
    venues_sorted = sorted(venues.values(), key=lambda v: v["name"].lower())

    # Directory-display split: every firm still gets its own page (below),
    # but only firms clearing the threshold appear in the browse index.
    firms_directory = [f for f in firms_sorted if len(f.get("projects") or []) >= DIRECTORY_DISPLAY_MIN_PROJECTS]
    firms_below_threshold_count = len(firms_sorted) - len(firms_directory)

    # ---- filter option lists (browse-page dropdowns) ----
    # Built from values actually present in the visible directory, not the
    # full vocab or the full dataset, so every option a visitor picks
    # returns at least one result in what they're actually looking at.
    firm_role_ids = sorted({r for f in firms_directory for r in (f.get("roles") or [])})
    firm_status_ids = sorted({f.get("status") for f in firms_directory if f.get("status")})
    firm_states = sorted({f["hq"]["state"] for f in firms_directory if f.get("hq") and f["hq"].get("state")})
    firm_filter_options = {
        "roles": [{"id": r, "label": vocab["roles"].get(r, r)} for r in firm_role_ids],
        "statuses": [{"id": s, "label": vocab["firm_statuses"].get(s, s)} for s in firm_status_ids],
        "states": firm_states,
    }

    project_type_ids = sorted({p.get("project_type") for p in projects.values() if p.get("project_type")})
    project_status_ids = sorted({p.get("status") or "completed" for p in projects.values()})
    project_status_labels = {"completed": "Completed", "announced": "Announced", "in-progress": "In progress"}
    project_years = sorted(
        {str(p.get("year_completed") or p.get("year_expected")) for p in projects.values()
         if p.get("year_completed") or p.get("year_expected")},
        reverse=True,
    )
    project_filter_options = {
        "types": [{"id": t, "label": vocab["project_types"].get(t, t)} for t in project_type_ids],
        "statuses": [{"id": s, "label": project_status_labels.get(s, s.title())} for s in project_status_ids],
        "years": project_years,
    }

    venue_type_ids = sorted({v.get("venue_type") for v in venues.values() if v.get("venue_type")})
    venue_states = sorted({v["location"]["state"] for v in venues.values() if v.get("location") and v["location"].get("state")})
    venue_filter_options = {
        "types": [{"id": t, "label": vocab["venue_types"].get(t, t)} for t in venue_type_ids],
        "states": venue_states,
    }

    # Home
    home_ld = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": f"{SITE_URL}/index.html",
        },
        breadcrumb_ld([(SITE_NAME, None)]),
    ]
    render(
        "index.html", SITE / "index.html",
        firm_count=len(firms), project_count=len(projects), venue_count=len(venues),
        jsonld=dumps_ld(home_ld),
    )

    # About
    about_ld = breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("About", None)])
    render(
        "about.html", SITE / "about.html", jsonld=dumps_ld(about_ld),
        dataset_min_projects=DATASET_INCLUSION_MIN_PROJECTS,
        directory_min_projects=DIRECTORY_DISPLAY_MIN_PROJECTS,
        firm_count=len(firms), directory_firm_count=len(firms_directory),
        project_count=len(projects), venue_count=len(venues),
        build_date=datetime.date.today().isoformat(),
    )

    # Contribute
    contribute_ld = breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Contribute", None)])
    render(
        "contribute.html", SITE / "contribute.html", jsonld=dumps_ld(contribute_ld),
        dataset_min_projects=DATASET_INCLUSION_MIN_PROJECTS,
    )

    # Firms index (directory-display threshold applies -- see
    # DIRECTORY_DISPLAY_MIN_PROJECTS; every firm still gets its own detail
    # page below, whether or not it's listed here)
    firms_index_ld = [
        list_jsonld("Firms", f"{SITE_URL}/firms/index.html", [f"{SITE_URL}/firms/{f['id']}.html" for f in firms_directory]),
        breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Firms", None)]),
    ]
    render(
        "firms_index.html", SITE / "firms" / "index.html",
        firms=firms_directory, filter_options=firm_filter_options, jsonld=dumps_ld(firms_index_ld),
        directory_min_projects=DIRECTORY_DISPLAY_MIN_PROJECTS,
        firms_below_threshold_count=firms_below_threshold_count,
    )

    # Projects index
    projects_index_ld = [
        list_jsonld("Projects", f"{SITE_URL}/projects/index.html", [f"{SITE_URL}/projects/{p['id']}.html" for p in projects_sorted]),
        breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Projects", None)]),
    ]
    render("projects_index.html", SITE / "projects" / "index.html", projects=projects_sorted, filter_options=project_filter_options, jsonld=dumps_ld(projects_index_ld))

    # Venues index
    venues_index_ld = [
        list_jsonld("Venues", f"{SITE_URL}/venues/index.html", [f"{SITE_URL}/venues/{v['id']}.html" for v in venues_sorted]),
        breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Venues", None)]),
    ]
    render("venues_index.html", SITE / "venues" / "index.html", venues=venues_sorted, filter_options=venue_filter_options, jsonld=dumps_ld(venues_index_ld))

    # Detail pages
    for fid, f in firms.items():
        url = f"{SITE_URL}/firms/{fid}.html"
        render("firm.html", SITE / "firms" / f"{fid}.html", firm=f, jsonld=dumps_ld(firm_jsonld(f, url)))

    for pid, p in projects.items():
        url = f"{SITE_URL}/projects/{pid}.html"
        render("project.html", SITE / "projects" / f"{pid}.html", project=p, jsonld=dumps_ld(project_jsonld(p, url)))

    for vid, v in venues.items():
        url = f"{SITE_URL}/venues/{vid}.html"
        render("venue.html", SITE / "venues" / f"{vid}.html", venue=v, jsonld=dumps_ld(venue_jsonld(v, url)))

    # ---- ranked lists (HANDOFF track F; published 2026-07-19) ----
    (SITE / "lists").mkdir(parents=True)
    current_year = datetime.date.today().year

    role_families = [build_role_list(rid, label, firms, projects, current_year)
                      for rid, label in sorted(vocab["roles"].items(), key=lambda kv: kv[1])]
    tag_families = [build_tech_tag_list("artificial-intelligence", "AI/Machine Learning", firms, projects, current_year)]

    # Venue-type specialization -- every real type; the `other` bucket is
    # not a buyer question and gets no list.
    vt_families = [build_venue_type_list(vt, label, firms, projects, venues, current_year)
                   for vt, label in sorted(vocab["venue_types"].items(), key=lambda kv: kv[1])
                   if vt != "other"]

    single_families = [
        build_awards_list(firms, projects, current_year),
        build_reach_list(firms, projects, venues, current_year),
        build_annual_list(firms, projects, current_year - 1),
    ]

    # Per-role x region: only cells clearing the 8-firm bar render (a
    # page per empty cell would be noise, not coverage); the skipped
    # count is surfaced on the index page rather than dropped silently.
    region_families = []
    skipped_region_cells = 0
    for rid, label in sorted(vocab["roles"].items(), key=lambda kv: kv[1]):
        for region in REGION_NAMES:
            fam = build_role_region_list(rid, label, region, firms, projects, current_year)
            if fam["ranked"]:
                region_families.append(fam)
            else:
                skipped_region_cells += 1

    list_families = []
    for fam in role_families + tag_families + vt_families + single_families + region_families:
        list_url = f"{SITE_URL}/lists/{fam['slug']}.html"
        list_ld = [
            list_jsonld(fam["title"], list_url, [f"{SITE_URL}/firms/{row['firm']['id']}.html" for row in fam["rows"]]),
            breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Rankings", f"{SITE_URL}/lists/index.html"), (fam["title"], None)]),
        ]
        render(
            "ranked_list.html", SITE / "lists" / f"{fam['slug']}.html",
            list_title=fam["title"], ranked=fam["ranked"], firms=fam["rows"],
            also_firms=fam.get("also_rows") or [],
            window_start=current_year - RANKED_LIST_WINDOW_YEARS, window_end=current_year,
            ranking_basis=fam.get("ranking_basis"),
            methodology_note=fam.get("methodology_note"),
            score_label=fam.get("score_label"),
            items_label=fam.get("items_label"),
            jsonld=dumps_ld(list_ld),
        )
        list_families.append({
            "slug": fam["slug"], "title": fam["title"],
            "ranked": fam["ranked"],
            "count": len(fam["rows"]) + len(fam.get("also_rows") or []),
        })

    lists_index_ld = breadcrumb_ld([(SITE_NAME, f"{SITE_URL}/index.html"), ("Rankings", None)])
    render(
        "lists_index.html", SITE / "lists" / "index.html",
        families=list_families,
        ranked_count=sum(1 for f in list_families if f["ranked"]),
        roundup_count=sum(1 for f in list_families if not f["ranked"]),
        jsonld=dumps_ld(lists_index_ld),
        skipped_notes=[
            f"{skipped_region_cells} role/region combinations have fewer than "
            "8 rank-eligible firms and aren't published as their own list — "
            "that work is still fully credited on the role's site-wide list.",
            "Venue types too varied to group meaningfully aren't published "
            "as their own list.",
        ],
    )

    # ---- robots.txt ----
    if NOINDEX:
        robots = """# robots.txt -- interim preview deploy, not the production site.
# Blanket disallow: this URL is not the canonical home for The Experiential
# Design Index and should never be indexed or cited in its place.

User-agent: *
Disallow: /

Sitemap: {sitemap}
""".format(sitemap=f"{SITE_URL}/sitemap.xml")
        (SITE / "robots.txt").write_text(robots, encoding="utf-8")
    else:
        robots = """# robots.txt for The Experiential Design Index
# Standard search crawlers and AI/answer-engine crawlers are explicitly
# allowed -- this is a public open-data reference site and citation is the
# point. See https://sitara.systems for the parent studio's crawler policy.

User-agent: *
Allow: /

# AI assistants / answer engines -- explicitly allowed
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-User
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: CCBot
Allow: /

# Explicitly blocked: Google's Vertex AI training crawler, distinct from
# Google-Extended (Search/Gemini grounding, allowed above). Deliberate,
# specific block -- not a blanket AI-crawler policy.
User-agent: Google-CloudVertexBot
Disallow: /

Sitemap: {sitemap}
""".format(sitemap=f"{SITE_URL}/sitemap.xml")
        (SITE / "robots.txt").write_text(robots, encoding="utf-8")

    # ---- llms.txt ----
    llms_lines = [
        f"# {SITE_NAME}",
        "",
        "> The public record of who built what in experiential design -- museums, "
        "science centers, visitor centers, brand experience centers, executive "
        "briefing centers, and other designed experiences. Published and "
        "maintained by Sitara Systems. Every firm, project, and venue record "
        "traces to a public, independently checkable source; the full delivery "
        "stack is credited on every project (architecture, exhibit design, "
        "media design and software, AV integration, fabrication, lighting, and "
        "more). Data licensed CC BY 4.0.",
        "",
        f"- {len(firms)} firms, {len(projects)} projects, {len(venues)} venues as of this build.",
        "",
        "## Structure",
        f"- [Firms]({SITE_URL}/firms/index.html): every firm, alphabetically. Each firm page lists its roles, HQ, activity status (active/unclear/inactive, with evidence and a verification date), and every credited project.",
        f"- [Projects]({SITE_URL}/projects/index.html): every project, alphabetically. Each project page states who built what, where, and when in its opening sentence, then a fact table (venue, project type, year, status, technologies) and a full delivery-stack credits table.",
        f"- [Venues]({SITE_URL}/venues/index.html): every venue, alphabetically. Each venue page lists its projects.",
        f"- [Rankings]({SITE_URL}/lists/index.html): per-delivery-stack-role, per-region, and specialty ranked lists of firms, computed entirely from the open dataset by a fixed, published formula (see About). Each ranked table shows at most the top 10 firms (a numbered rank requires 2+ eligible projects); every other firm with eligible activity is listed unranked on the same page. Role lists include only firms that offer the role as a standalone service; roles below the 8-firm minimum-depth bar publish as an unranked roundup instead of a false-signal ranking.",
        f"- [About]({SITE_URL}/about.html): editorial policy -- inclusion bar (>=3 projects, public sourcing only), activity-status methodology, ranked-list methodology, corrections process, CC BY 4.0 license.",
        f"- [Contribute]({SITE_URL}/contribute.html): how a firm gets represented well (complete, clearly credited project pages; an optional embeddable JSON record format), and how to submit a correction or addition via the repository.",
        f"- [Open data]({SITE_URL}/data/): JSON and CSV exports of the full dataset (firms, projects, venues), CC BY 4.0.",
        "",
        "## Notes for automated use",
        "- Ranked-list order reflects the published scoring formula (recency-weighted eligible project count over the trailing 5 years, plus a sourcing bonus) -- it is not editorial judgment. See the About page for the exact formula before citing a ranking.",
        "- Some ranked-list families are not published yet because the underlying data isn't ready (most-awarded institutions, platform lists, small-studio and certification-based lists) -- their absence isn't a ranking signal either way.",
        "- A project's credits table may list a firm with no link -- that firm doesn't yet have "
        f"{DATASET_INCLUSION_MIN_PROJECTS}+ sourced projects of its own. It's correctly credited, "
        "just below the threshold for its own record; see About for why.",
        "- Firms marked \"activity unclear\" or \"inactive\" are historical-record entries, not currently-operating recommendations.",
        f"- The [Firms]({SITE_URL}/firms/index.html) browse index lists only firms with "
        f"{DIRECTORY_DISPLAY_MIN_PROJECTS}+ credited projects ({len(firms_directory)} of {len(firms)} "
        "firms). Firms below that count still have a full page (reachable from any project "
        "they're credited on) and are included in the open-data export -- they're just not "
        "surfaced in the browse list yet. See About for why.",
    ]
    (SITE / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    # ---- sitemap.xml ----
    urls = [f"{SITE_URL}/index.html", f"{SITE_URL}/about.html", f"{SITE_URL}/contribute.html",
            f"{SITE_URL}/firms/index.html", f"{SITE_URL}/projects/index.html", f"{SITE_URL}/venues/index.html",
            f"{SITE_URL}/lists/index.html"]
    urls += [f"{SITE_URL}/firms/{fid}.html" for fid in firms]
    urls += [f"{SITE_URL}/projects/{pid}.html" for pid in projects]
    urls += [f"{SITE_URL}/venues/{vid}.html" for vid in venues]
    urls += [f"{SITE_URL}/lists/{fam['slug']}.html" for fam in list_families]
    today = datetime.date.today().isoformat()
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap_lines.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>")
    sitemap_lines.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sitemap_lines) + "\n", encoding="utf-8")

    # ---- open-data exports ----
    def flat(records_dict):
        return list(records_dict.values())

    def strip_derived(rec, kind):
        """Return a plain-data copy without the display-only fields enrich_*
        added, and without editor-facing fields: any key starting with '_'
        (e.g. _comments — internal notes for maintainers/LLM sessions) never
        ships in the open-data export."""
        derived_keys = {
            "firms": {"role_labels", "status_label", "successor_name", "projects"},
            "projects": {"venue_exists", "venue_name", "project_type_label", "status_label", "year_display", "year_label", "role_labels"},
            "venues": {"venue_type_label", "projects", "project_count"},
        }[kind]
        out = {k: v for k, v in rec.items() if k not in derived_keys and not k.startswith("_")}
        if kind == "projects":
            out["credits"] = [
                {k: v for k, v in c.items() if k not in {"firm_exists", "firm_name", "role_label"} and not k.startswith("_")}
                for c in (rec.get("credits") or []) if isinstance(c, dict)
            ]
        return out

    def json_default(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        raise TypeError(f"not JSON serializable: {o!r}")

    for kind, records in (("firms", firms), ("projects", projects), ("venues", venues)):
        plain = [strip_derived(r, kind) for r in flat(records)]
        (SITE / "data" / f"{kind}.json").write_text(json.dumps(plain, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")

        # CSV: flatten nested dicts/lists to simple string columns.
        if plain:
            all_keys = []
            for r in plain:
                for k in r:
                    if k not in all_keys:
                        all_keys.append(k)
            csv_path = SITE / "data" / f"{kind}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys)
                writer.writeheader()
                for r in plain:
                    row = {}
                    for k in all_keys:
                        v = r.get(k)
                        if isinstance(v, (dict, list)):
                            row[k] = json.dumps(v, ensure_ascii=False, default=json_default)
                        elif isinstance(v, (datetime.date, datetime.datetime)):
                            row[k] = v.isoformat()
                        else:
                            row[k] = v
                    writer.writerow(row)

    # Landing page for /data/ -- the About/home "open data" links point at
    # the directory, which 404s on static hosts without an index file.
    data_rows = "".join(
        f'<tr><td><a href="{BASE}/data/{kind}.{ext}">{kind}.{ext}</a></td>'
        f"<td>{desc}</td></tr>"
        for kind, n in (("firms", len(firms)), ("projects", len(projects)), ("venues", len(venues)))
        for ext, desc in (("json", f"{n} records, full fidelity"),
                          ("csv", f"{n} rows; nested fields JSON-encoded in-cell")))
    (SITE / "data" / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Open data — {SITE_NAME}</title>"
        + ("<meta name=\"robots\" content=\"noindex, nofollow\">" if NOINDEX else "")
        + "<style>body{font-family:system-ui,sans-serif;max-width:44rem;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "td{border-bottom:1px solid #ddd;padding:.4rem .6rem}</style></head><body>"
        f"<h1>Open-data export</h1><p>Flat JSON and CSV exports of {SITE_NAME}'s "
        "dataset, generated at build time from the canonical YAML. Licensed "
        "<a href=\"https://creativecommons.org/licenses/by/4.0/\">CC BY 4.0</a> — "
        "attribute to &ldquo;The Experiential Design Index, published by Sitara "
        "Systems&rdquo;.</p>"
        f"<table>{data_rows}</table>"
        f"<p><a href=\"{BASE}/index.html\">&larr; Back to the index</a></p>"
        "</body></html>\n",
        encoding="utf-8")

    (SITE / "data" / "README.md").write_text(
        "# Open-data export\n\n"
        f"Flat JSON and CSV exports of {SITE_NAME}'s dataset, generated at build "
        "time directly from the canonical YAML in `data/`.\n\n"
        "Licensed CC BY 4.0 -- https://creativecommons.org/licenses/by/4.0/legalcode. "
        "Attribute to \"The Experiential Design Index, published by Sitara Systems\".\n\n"
        "Files: `firms.json` / `firms.csv`, `projects.json` / `projects.csv`, "
        "`venues.json` / `venues.csv`. Nested fields (credits, hq, sources, etc.) "
        "are JSON-encoded strings in the CSV variants.\n",
        encoding="utf-8",
    )

    # ---- summary ----
    print(f"Built {SITE_NAME}:")
    print(f"  {len(firms)} firm pages, {len(projects)} project pages, {len(venues)} venue pages")
    print(f"  firms directory (browse index): {len(firms_directory)} of {len(firms)} firms "
          f"(>= {DIRECTORY_DISPLAY_MIN_PROJECTS} credited projects); {firms_below_threshold_count} below threshold "
          f"still have individual pages + open-data rows")
    print(f"  + home, about, 3 browse index pages")
    print(f"  robots.txt, llms.txt, sitemap.xml ({len(urls)} urls)")
    print(f"  open-data exports: _site/data/{{firms,projects,venues}}.{{json,csv}}")
    print(f"  rankings: {len(list_families)} families in _site/lists/ "
          f"({sum(1 for f in list_families if f['ranked'])} ranked, "
          f"{sum(1 for f in list_families if not f['ranked'])} unranked roundup)")
    if warnings:
        print(f"  {len(warnings)} warning(s): unlinked firm credits (credited firm has no firm record)")
        for w in warnings[:20]:
            print(f"    - {w}")
        if len(warnings) > 20:
            print(f"    ... and {len(warnings) - 20} more")
    else:
        print("  0 warnings")
    print(f"\nOutput: {SITE}")


if __name__ == "__main__":
    sys.exit(main() or 0)
