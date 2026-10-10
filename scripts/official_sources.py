"""Reviewed replacements for broken maintained URLs; exact URL matches only.

These are source repairs, not guessed CFP paths. Edition checks still apply.
"""
REPAIRS = {
    ('cscwd', 'http://2027.cscwd.org'): ('https://cscwd2027.dailyeliteevents.com.au/', 'Organizing site identifies CSCWD 2027, its working group and university organizers; old host times out.'),
    ('icc', 'https://icc2027.ieee-icc.org'): ('https://www.comsoc.org/conferences-events/ieee-international-conference-communications-2027', 'IEEE Communications Society organizer lists ICC 2027; conference host fails certificate validation.'),
    ('sacmat', 'https://www.sacmat.org/2027/'): ('https://www.sacmat.org/2027/index.php', 'Directory index returns 404; official index.php identifies SACMAT 2027.'),
    ('icws', 'https://services.conferences.computer.org/2026/icws-2026/'): ('https://services.conferences.computer.org/2026/icws/', 'Official SERVICES navigation and ICWS flyer link to /2026/icws/.'),
    ('fse', 'https://fseconf.org'): ('https://conf.researchr.org/track/fse-2027/fse-2027-papers', 'Official FSE series directory links to the Researchr 2027 conference.'),
    ('inscrypt', 'https://inscrypt2026.comp.polyu.edu.hk/call-for-papers'): ('https://inscrypt2026.comp.polyu.edu.hk/call-for-papers/', 'Canonical trailing slash avoids a redirect through HTTP.'),
}


def repaired_source(slug, url):
    return REPAIRS.get((slug, url))
