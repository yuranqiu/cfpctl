#!/usr/bin/env python3
"""Full refresh: download ALL categories using raw GitHub URLs (no API needed).
Keeps all historical years. Merges with existing manually-curated track data."""

import yaml
import os
import re
from datetime import datetime, timezone
from urllib.request import urlopen, Request

RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference"

# All file lists discovered from previous API calls
CATEGORY_FILES = {
    "AI": ("ai.yaml", ["ai"], [
        "aaai.yml","aamas.yml","accv.yml","acl.yml","acml.yml","aistats.yml","alt.yml",
        "bmvc.yml","cec.yml","cicai.yml","coling.yml","colm.yml","colt.yml","conll.yml",
        "corl.yml","cpal.yml","cvc.yml","cvpr.yml","dai.yml","eacl.yml","ecai.yml",
        "eccv.yml","emnlp.yml","esann.yml","eurogp.yml","euvip.yml","evoapps.yml",
        "evocop.yml","evomusart.yml","fg.yml","gecco.yml","icann.yml","icaps.yml",
        "iccbr.yml","iccv.yml","icdar.yml","iclr.yml","icml.yml","iconip.yml","icpr.yml",
        "icra.yml","ictai.yml","ijcai.yml","ijcb.yml","ijcnlp.yml","ijcnn.yml","iros.yml",
        "kr.yml","ksem.yml","log.yml","naacl.yml","nips.yml","nlpcc.yml","ppsn.yml",
        "pricai.yml","probml.yml","rss.yml","rulemlrr.yml","uai.yml","wacv.yml"
    ]),
    "CG": ("graphics.yaml", ["vision", "graphics"], [
        "3dv.yml","casa.yml","cccg.yml","cgi.yml","cog.yml","cvm.yml","dcc.yml","eg.yml",
        "egsr.yml","eurovis.yml","eusipco.yml","gmp.yml","icassp.yml","icip.yml","icme.yml",
        "icmr.yml","icvrv.yml","interspeech.yml","ismar.yml","mm.yml","mmasia.yml","mmm.yml",
        "ncmmsc.yml","pacificvis.yml","pg.yml","prcv.yml","sca.yml","sgp.yml","sig.yml",
        "siga.yml","slt.yml","smi.yml","spm.yml","vinci.yml","vis.yml","vr.yml"
    ]),
    "CT": ("theory.yaml", ["theory"], [
        "cade.yml","cav.yml","ccc.yml","cocoon.yml","concur.yml","esa.yml","fmcad.yml",
        "focs.yml","fscd.yml","hscc.yml","icalp.yml","ijcar.yml","isaac.yml","isit.yml",
        "lics.yml","sat.yml","setta.yml","socg.yml","soda.yml","stoc.yml"
    ]),
    "DB": ("database.yaml", ["database"], [
        "adma.yml","apweb.yml","cidr.yml","cikm.yml","dasfaa.yml","ecir.yml","edbt.yml",
        "icde.yml","icdm.yml","icdt.yml","iswc.yml","pakdd.yml","pkdd.yml","pods.yml",
        "recsys.yml","sdm.yml","sigir.yml","sigkdd.yml","sigmod.yml","vldb.yml","wisa.yml",
        "wise.yml","wsdm.yml"
    ]),
    "DS": ("systems.yaml", ["systems"], [
        "appt.yml","apsys.yml","asap.yml","aspdac.yml","asplos.yml","atc.yml","ats.yml",
        "ccgrid.yml","cf.yml","cgo.yml","cluster.yml","codesisss.yml","dac.yml","date.yml",
        "ets.yml","europar.yml","eurosys.yml","fast.yml","fccm.yml","fpga.yml","fpt.yml",
        "glsvlsi.yml","hipeac.yml","hotchips.yml","hotstorage.yml","hpca.yml","hpcc.yml",
        "hpdc.yml","ica3pp.yml","iccad.yml","iccd.yml","icdcs.yml","icpads.yml","icpp.yml",
        "ics.yml","iiswc.yml","ipdps.yml","isca.yml","iscas.yml","ispa.yml","ispd.yml",
        "itc-asia.yml","itc.yml","jcc.yml","lisa.yml","micro.yml","msst.yml","netys.yml",
        "pact.yml","pdcat.yml","performance.yml","podc.yml","ppopp.yml","rtas.yml","sc.yml",
        "sec.yml","sigmetrics.yml","socc.yml","spaa.yml","systor.yml","vee.yml"
    ]),
    "SC": ("security.yaml", ["security"], [
        "acisp.yml","acns.yml","acsac.yml","asiaccs.yml","asiacrypt.yml","blocksys.yml",
        "ccs.yml","ches.yml","codaspy.yml","crypto.yml","cscloud.yml","csfw.yml","ct-rsa.yml",
        "dfrws-apac.yml","dfrws.yml","dimva.yml","dsn.yml","esorics.yml","eurocrypt.yml",
        "eurosp.yml","fc.yml","fse.yml","hotsec.yml","icdf2c.yml","icics.yml","ifip119.yml",
        "ih&mmsec.yml","indocrypt.yml","inscrypt.yml","isc.yml","ndss.yml","noms.yml",
        "nspw.yml","pam.yml","pets.yml","pkc.yml","raid.yml","sac.yml","sacmat.yml",
        "satml.yml","sec.yml","securecomm.yml","soups.yml","sp.yml","srds.yml","tcc.yml",
        "trustcom.yml","uss.yml","wisec.yml"
    ]),
    "SE": ("software.yaml", ["software"], [
        "aplas.yml","apsec.yml","ase.yml","atva.yml","caise.yml","compsac.yml","cp.yml",
        "ease.yml","ecoop.yml","esem.yml","etaps.yml","fm.yml","fse.yml","hotos.yml",
        "iceccs.yml","icfem.yml","icfp.yml","icpc.yml","icse.yml","icsme.yml","icsoc.yml",
        "icst.yml","icws.yml","internetware.yml","ispass.yml","issre.yml","issta.yml",
        "lctes.yml","middleware.yml","models.yml","msr.yml","oopsla.yml","osdi.yml","pepm.yml",
        "pldi.yml","popl.yml","qrs.yml","re.yml","refsq.yml","rv.yml","saner.yml","sas.yml",
        "scam.yml","seke.yml","sosp.yml","sse.yml","tase.yml","vmcai.yml"
    ]),
}


def fetch_yaml(url):
    req = Request(url, headers={"User-Agent": "cfpctl-convert/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return yaml.safe_load(resp.read().decode("utf-8"))
    except Exception as e:
        return None


def parse_timezone(tz_str):
    if not tz_str:
        return "-12:00"
    tz_str = tz_str.strip()
    m = re.match(r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$', tz_str, re.IGNORECASE)
    if m:
        sign, hours, minutes = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        return f"{sign}{hours:02d}:{minutes:02d}"
    return "-12:00"


def convert_datetime(dt_str, tz_suffix):
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    if dt_str.upper() in ("TBD", "TBA", "UNKNOWN", ""):
        return None
    if 'T' in dt_str and ('+' in dt_str[10:] or dt_str.endswith('Z')):
        return dt_str
    if ' ' in dt_str:
        dt_str_clean = dt_str.replace(' ', 'T')
    else:
        dt_str_clean = dt_str + "T00:00:00"
    return f"{dt_str_clean}{tz_suffix}"


def convert_conference(data, fields):
    if not isinstance(data, dict):
        return []
    rank_info = data.get("rank", {})
    if not isinstance(rank_info, dict):
        return []
    ccf_rank = rank_info.get("ccf")
    if not ccf_rank or ccf_rank not in ("A", "B", "C"):
        return []
    core_rank = rank_info.get("core")
    title = data.get("title", "").strip()
    if not title:
        return []
    slug = title.lower().replace(" ", "-")
    confs = data.get("confs", [])
    if not confs:
        return []

    latest_conf = max((c for c in confs if isinstance(c, dict)), key=lambda c: int(c.get("year", 0)), default=None)
    if latest_conf is None:
        return []

    homepage = latest_conf.get("link", "")
    location = latest_conf.get("place", "TBD") or "TBD"

    sorted_confs = sorted([c for c in confs if isinstance(c, dict)], key=lambda c: int(c.get("year", 0)))
    cycles = []
    for conf in sorted_confs:
        try:
            year = int(conf.get("year", 0))
        except (ValueError, TypeError):
            continue
        tz_suffix = parse_timezone(conf.get("timezone", ""))
        timelines = conf.get("timeline", [])
        if not timelines:
            continue
        for tl in timelines:
            if not isinstance(tl, dict):
                continue
            deadline_iso = convert_datetime(tl.get("deadline"), tz_suffix)
            abstract_iso = convert_datetime(tl.get("abstract_deadline"), tz_suffix)
            notification_iso = convert_datetime(tl.get("notification"), tz_suffix) if tl.get("notification") else None
            if not deadline_iso:
                continue
            cycle = {"name": str(year)}
            if abstract_iso:
                cycle["abstract"] = abstract_iso
            cycle["deadline"] = deadline_iso
            if notification_iso:
                cycle["notification"] = notification_iso
            cycles.append(cycle)

    if not cycles:
        return []

    entry = {
        "name": title, "slug": slug,
        "rank": {},
        "fields": list(fields),
        "homepage": homepage or "",
        "location": location,
        "cycles": cycles,
    }
    if ccf_rank:
        entry["rank"]["ccf"] = ccf_rank
    if core_rank:
        entry["rank"]["core"] = core_rank
    return [entry]


def merge_with_existing(new_confs, existing_file):
    """Merge new data with existing file, preserving manual track data and verified flags."""
    if not os.path.exists(existing_file):
        return new_confs

    with open(existing_file) as f:
        existing = yaml.safe_load(f) or []

    # Build map of existing entries by slug
    existing_map = {c["slug"]: c for c in existing}

    merged = []
    seen_slugs = set()

    # First: keep existing entries that have manual tracks or verified flag
    for conf in existing:
        slug = conf["slug"]
        has_tracks = any("tracks" in cyc for cyc in conf.get("cycles", []))
        is_verified = conf.get("verified", False)
        if has_tracks or is_verified:
            merged.append(conf)
            seen_slugs.add(slug)

    # Then: add new entries that aren't already in merged
    for conf in new_confs:
        slug = conf["slug"]
        if slug not in seen_slugs:
            merged.append(conf)
            seen_slugs.add(slug)

    merged.sort(key=lambda c: c["name"].lower())
    return merged


def main():
    output_dir = "/app/data"
    total = 0

    for category, (output_file, fields, files) in CATEGORY_FILES.items():
        print(f"\n{'='*60}")
        print(f"Processing {category} -> {output_file} ({len(files)} files)")
        print(f"{'='*60}")

        all_confs = []
        for filename in sorted(files):
            url = f"{RAW_BASE}/{category}/{filename}"
            data = fetch_yaml(url)
            if data is None:
                print(f"  SKIP {filename}")
                continue
            results = []
            if isinstance(data, list):
                for entry in data:
                    results.extend(convert_conference(entry, fields))
            elif isinstance(data, dict):
                results.extend(convert_conference(data, fields))
            if results:
                all_confs.extend(results)
                print(f"  OK {filename} ({len(results)})")
            else:
                print(f"  skip {filename}")

        # Deduplicate
        seen = set()
        unique = []
        for c in all_confs:
            if c["slug"] not in seen:
                seen.add(c["slug"])
                unique.append(c)

        # Merge with existing data (preserve manual tracks)
        outpath = os.path.join(output_dir, output_file)
        merged = merge_with_existing(unique, outpath)

        with open(outpath, "w", encoding="utf-8") as f:
            yaml.dump(merged, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

        print(f"  Wrote {len(merged)} conferences to {outpath} (new: {len(unique)}, merged: {len(merged)})")
        total += len(merged)

    print(f"\n{'='*60}")
    print(f"TOTAL: {total} conferences across all categories")


if __name__ == "__main__":
    main()
