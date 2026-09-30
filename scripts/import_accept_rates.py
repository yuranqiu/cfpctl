#!/usr/bin/env python3
"""Import acceptance rates from ccfddl into cfpctl YAML data files."""

import yaml
import os
import glob
from urllib.request import urlopen, Request

RAW_BASE = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/accept_rates"

CATEGORIES = {
    "AI": "ai.yaml", "CG": "graphics.yaml", "CT": "theory.yaml",
    "DB": "database.yaml", "DS": "systems.yaml", "HI": "hci.yaml",
    "MX": "interdisciplinary.yaml", "NW": "network.yaml",
    "SC": "security.yaml", "SE": "software.yaml",
}

# Map ccfddl accept_rates filenames to cfpctl slugs
SLUG_OVERRIDES = {
    "nips": "neurips",
    "sigkdd": "kdd",
    "sp": "ieee-sp",
    "uss": "usenix-security",
    "sec": "ifip-sec",
    "fse": "fse-crypto",  # In SC category, FSE = Fast Software Encryption
}


def fetch_yaml(url):
    req = Request(url, headers={"User-Agent": "cfpctl/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return yaml.safe_load(resp.read().decode("utf-8"))
    except Exception:
        return None


def main():
    data_dir = "/app/data"
    # Build slug->file map from existing data
    slug_to_file = {}
    for cat, filename in CATEGORIES.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath) as f:
            confs = yaml.safe_load(f) or []
        for c in confs:
            slug_to_file[c["slug"]] = filepath

    updated = 0
    skipped = 0

    for cat, out_file in CATEGORIES.items():
        print(f"\nProcessing {cat}...")
        # Fetch directory listing via raw URL pattern - try known files
        # Since we can't list directories without API, use the file list from research
        cat_files = {
            "AI": ["aaai","aamas","acl","aistats","alt","bmvc","cec","coling","colt","conll","cvpr","dai","ecai","eccv","emnlp","eurogp","fg","gecco","icann","icaps","iccbr","iccv","icdar","iclr","icml","iconip","icpr","icra","ictai","ijcai","ijcb","ijcnlp","ijcnn","iros","kr","ksem","naacl","nips","nlpcc","ppsn","pricai","rss","rulemlrr","uai","wacv"],
            "CG": ["3dv","cgi","eg","egsr","eurovis","gmp","icassp","icip","icme","icmr","interspeech","ismar","mm","mmm","ncmmsc","pacificvis","pg","prcv","sca","sgp","sig","slt","smi","spm","vis","vr"],
            "CT": ["cade","cav","ccc","cocoon","concur","esa","fmcad","focs","fscd","hscc","icalp","ijcar","isaac","lics","sat","setta","socg","soda","stoc"],
            "DB": ["adma","apweb","cikm","dasfaa","ecir","edbt","icde","icdm","icdt","iswc","pakdd","pkdd","pods","recsys","sdm","sigir","sigkdd","sigmod","vldb","wise","wsdm"],
            "DS": ["appt","apsys","asap","aspdac","asplos","atc","ats","ccgrid","cf","cgo","dac","date","europar","eurosys","fast","fpga","hotstorage","hpca","hpdc","ica3pp","iccad","ics","iiswc","isca","iscas","itc-asia","itc","lisa","micro","netys","pdcat","performance","ppopp","rtas","sc","sec","sigmetrics","systor","vee"],
            "HI": ["assets","chi","collaboratecom","cscw","cscwd","dis","group","hicss","icmi","idc","iss","iui","mobilehci","percom","ubicomp","uist"],
            "MX": ["aft","bibm","bis","cloud","cogsci","emsoft","icaif","icic","isbra","ismb","miccai","mlsys","recomb","rtss","sai-computing","sigcse","sigspatial","wine","www"],
            "NW": ["apnet","conext","forte","globecom","hotnets","imc","infocom","mmsys","mobicom","mobihoc","mobisys","nsdi","sensys","sigcomm"],
            "SC": ["acisp","acns","acsac","asiaccs","ccs","crypto","ct-rsa","dimva","dsn","esorics","eurocrypt","eurosp","fc","fse","icdf2c","icics","ih&mmsec","indocrypt","inscrypt","isc","ndss","noms","pets","pkc","raid","sac","soups","sp","srds","tcc","uss","wisec"],
            "SE": ["aplas","apsec","ase","atva","caise","compsac","cp","ease","ecoop","esem","etaps","fm","fse","hotos","iceccs","icfem","icfp","icpc","icse","icsme","icsoc","icst","icws","internetware","ispass","issre","issta","lctes","models","msr","oopsla","osdi","pepm","pldi","popl","qrs","re","refsq","rv","saner","sas","scam","seke","sosp","sse","tase","vmcai"],
        }

        files = cat_files.get(cat, [])
        for name in files:
            url = f"{RAW_BASE}/{cat}/{name}.yml"
            data = fetch_yaml(url)
            if not data or not isinstance(data, list) or len(data) == 0:
                skipped += 1
                continue

            entry = data[0]
            rates = entry.get("accept_rates", [])
            if not rates:
                skipped += 1
                continue

            # Get latest rate
            latest = max(rates, key=lambda r: r.get("year", 0))
            rate_str = latest.get("str", "")
            if not rate_str:
                rate_val = latest.get("rate", 0)
                submitted = latest.get("submitted", 0)
                accepted = latest.get("accepted", 0)
                year = latest.get("year", "?")
                if rate_val:
                    rate_str = f"{rate_val*100:.1f}% ({accepted}/{submitted} {str(year)[-2:]})"

            # Map to cfpctl slug
            slug = SLUG_OVERRIDES.get(name, name.lower())

            # Find which file has this slug
            target_file = slug_to_file.get(slug)
            if not target_file:
                # Try with hyphens
                slug_hyphen = name.lower().replace(" ", "-")
                target_file = slug_to_file.get(slug_hyphen)
            if not target_file:
                skipped += 1
                continue

            # Load and update the target file
            with open(target_file) as f:
                confs = yaml.safe_load(f) or []

            found = False
            for c in confs:
                if c["slug"] == slug or c["slug"] == name.lower():
                    c["accept_rate"] = rate_str
                    found = True
                    updated += 1
                    break

            if found:
                with open(target_file, "w") as f:
                    yaml.dump(confs, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
                print(f"  ✓ {name} -> {slug}: {rate_str}")
            else:
                skipped += 1

    print(f"\n{'='*60}")
    print(f"Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
