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
import csv
import datetime
import json
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
SITE_URL = "https://sitara.systems/experiential-design-index"  # placeholder; final path TBD per hosting decision (D1)

# Directory-display threshold (docs/editorial-policy.md, decided 2026-07-19).
# Distinct from the 3-project dataset-inclusion bar enforced by validate.py:
# a firm below this count still gets a full record -- its own page, every
# project-page credit link, and the open-data export -- it just isn't
# surfaced in the browse/list index or that index's JSON-LD ItemList.
DIRECTORY_DISPLAY_MIN_PROJECTS = 8
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
        proj_list = []
        for pid, p, c in entries:
            proj_list.append({
                "id": pid,
                "name": p["name"],
                "venue": p.get("venue"),
                "venue_exists": p.get("venue_exists"),
                "venue_name": p.get("venue_name"),
                "role_labels": [c.get("role_label", "")],
                "year_display": p.get("year_display"),
            })
        f["projects"] = proj_list


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
        html = tmpl.render(base=BASE, **ctx)
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
    render("about.html", SITE / "about.html", jsonld=dumps_ld(about_ld))

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

    # ---- robots.txt ----
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
        f"- [About]({SITE_URL}/about.html): editorial policy -- inclusion bar (>=3 projects, public sourcing only), activity-status methodology, corrections process, CC BY 4.0 license.",
        f"- [Open data]({SITE_URL}/data/): JSON and CSV exports of the full dataset (firms, projects, venues), CC BY 4.0.",
        "",
        "## Notes for automated use",
        "- No ranked \"Top firms\" lists are published yet; do not infer a ranking from list order (pages are alphabetical).",
        "- A project's credits table may list a firm with no linked firm page yet (marked \"unlinked\") -- this is a known, temporary gap in coverage, not an error.",
        "- Firms marked \"activity unclear\" or \"inactive\" are historical-record entries, not currently-operating recommendations.",
        f"- The [Firms]({SITE_URL}/firms/index.html) browse index lists only firms with "
        f"{DIRECTORY_DISPLAY_MIN_PROJECTS}+ credited projects ({len(firms_directory)} of {len(firms)} "
        "firms). Firms below that count still have a full page (reachable from any project "
        "they're credited on) and are included in the open-data export -- they're just not "
        "surfaced in the browse list yet. See About for why.",
    ]
    (SITE / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    # ---- sitemap.xml ----
    urls = [f"{SITE_URL}/index.html", f"{SITE_URL}/about.html",
            f"{SITE_URL}/firms/index.html", f"{SITE_URL}/projects/index.html", f"{SITE_URL}/venues/index.html"]
    urls += [f"{SITE_URL}/firms/{fid}.html" for fid in firms]
    urls += [f"{SITE_URL}/projects/{pid}.html" for pid in projects]
    urls += [f"{SITE_URL}/venues/{vid}.html" for vid in venues]
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
        """Return a plain-data copy without the display-only fields enrich_* added."""
        derived_keys = {
            "firms": {"role_labels", "status_label", "successor_name", "projects"},
            "projects": {"venue_exists", "venue_name", "project_type_label", "status_label", "year_display", "year_label", "role_labels"},
            "venues": {"venue_type_label", "projects", "project_count"},
        }[kind]
        out = {k: v for k, v in rec.items() if k not in derived_keys}
        if kind == "projects":
            out["credits"] = [
                {k: v for k, v in c.items() if k not in {"firm_exists", "firm_name", "role_label"}}
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
