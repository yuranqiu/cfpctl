"""Edition identity from explicit page headings, never from deadline dates."""
import re

ALIASES = {
    'aaai': r'AAAI', 's&p': r'(?:S&P|Security and Privacy)',
    'sigkdd': r'(?:SIGKDD|KDD)', 'www': r'(?:WWW|ACM Web|The Web Conference)',
    'acm-mm': r'(?:ACM Multimedia|ACM MM)', 'acm-siggraph': r'SIGGRAPH',
    'ieee-vis': r'(?:IEEE VIS|VIS)', 'ieee-vr': r'(?:IEEE VR|VR)',
}


def title_years(headings, conference):
    identity = ' '.join(text for tag, text in headings if tag in ('title', 'h1'))
    years = set(re.findall(r'\b20\d{2}\b', identity))
    slug = conference.get('slug', '')
    alias = ALIASES.get(slug, re.escape(slug).replace(r'\-', r'[ -]?'))
    if alias:
        years.update('20' + short for short in re.findall(
            rf'\b{alias}\s*[-\u2018\u2019\x27]\s*(\d{{2}})\b', identity, re.I))
    return years
