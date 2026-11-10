#!/usr/bin/env python3
# Usage (from repo root): python scripts/backfill_credit_sources.py [--write]
# Idempotent: credits that already carry sources are skipped. Dry run without --write.
"""Deterministic backfill of per-credit `sources`.
Rule A (first-party): a project source URL on the credited firm's own website domain.
Rule B (note-cited): credit note says "per <Firm>'s own ..." and a project source is on that firm's domain.
Text-level insertion so comments/formatting survive; re-parse verifies only `sources` was added."""
import yaml, glob, re, sys, urllib.parse, copy, collections
SHARED_HOSTS = {"cargocollective.com"}  # portfolio hosts: firm identity is the first path segment
def dom(u):
    sp = urllib.parse.urlsplit(u)
    n = sp.netloc.lower()
    n = n[4:] if n.startswith("www.") else n
    if n in SHARED_HOSTS:
        seg = sp.path.strip("/").split("/")[0].lower()
        n = n + "/" + seg
    return n
firms = {}
for f in glob.glob("data/firms/*.yaml"):
    d = yaml.safe_load(open(f, encoding="utf-8"))
    if d and d.get("website"): firms[d["id"]] = d
fdom = {fid: dom(d["website"]) for fid, d in firms.items()}
fdom.pop("lexington", None)  # Lexington's record says it shares Nassal's corporate site; nassal.com pages prove Nassal only
_cnt = collections.Counter(fdom.values())
fdom = {k: v for k, v in fdom.items() if _cnt[v] == 1}  # a domain shared by two firms (e.g. Nassal/Lexington) proves neither
names = {}
for fid, d in firms.items():
    for n in [d["name"]] + list(d.get("aka") or []):
        names[n.lower()] = fid
name_re = re.compile(r"per (?:the )?([A-Z][^,;.]*?)(?:'s|’s) own", re.I)
stats = collections.Counter(); changed = 0
for path in sorted(glob.glob("data/projects/*.yaml")):
    text = open(path, encoding="utf-8").read()
    rec = yaml.safe_load(text)
    if not rec or not rec.get("credits"): continue
    srcs = [s for s in (rec.get("sources") or []) if isinstance(s, str)]
    plan = {}
    for i, c in enumerate(rec["credits"]):
        if not isinstance(c, dict) or c.get("sources"): continue
        got = []
        fd = fdom.get(c.get("firm"))
        if fd:
            got += [s for s in srcs if dom(s) == fd]
            if got: stats["A"] += 1
        m = name_re.search(str(c.get("note") or ""))
        if m:
            oid = names.get(m.group(1).strip().lower())
            if oid and oid in fdom:
                b = [s for s in srcs if dom(s) == fdom[oid] and s not in got]
                if b: got += b; stats["B"] += 1
        if got: plan[i] = got
    if not plan: continue
    lines = text.split("\n")
    # locate credit entry start lines inside the credits block
    starts = []; in_cr = False
    for j, ln in enumerate(lines):
        if re.match(r"^credits:\s*$", ln): in_cr = True; continue
        if in_cr and re.match(r"^[^\s-]", ln): break
        if in_cr and re.match(r"^\s*- ", ln) and (not starts or len(ln) - len(ln.lstrip()) == starts[0][1]):
            starts.append((j, len(ln) - len(ln.lstrip())))
    if len(starts) != len(rec["credits"]):
        stats["skip_layout"] += 1; print("SKIP layout", path); continue
    for i in sorted(plan, reverse=True):
        j, dash = starts[i]; key = dash + 2
        end = starts[i + 1][0] if i + 1 < len(starts) else next((k for k in range(j + 1, len(lines)) if re.match(r"^[^\s-]", lines[k])), len(lines))
        role = next((k for k in range(j, end) if re.match(r"^\s*(- )?role:", lines[k])), None)
        if role is None: stats["skip_norole"] += 1; continue
        ins = [" " * key + "sources:"] + [" " * (key + 2) + "- " + s for s in plan[i]]
        lines[role + 1:role + 1] = ins
    new = "\n".join(lines)
    after = yaml.safe_load(new); exp = copy.deepcopy(rec)
    for i, g in plan.items(): exp["credits"][i]["sources"] = g
    if after != exp:
        stats["skip_verify"] += 1; print("SKIP verify", path); continue
    if "--write" in sys.argv: open(path, "w", encoding="utf-8", newline="").write(new)
    changed += 1; stats["credits"] += len(plan)
print(dict(stats), "files", changed)
