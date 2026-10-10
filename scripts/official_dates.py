"""Conservative parsing of explicit dates and times on official CFP pages.

No year or timezone is inferred from the machine's locale or current date.
"""
import re
from datetime import date as calendar_date, datetime

_MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?'
_DAY = r'\d{1,2}(?:st|nd|rd|th)?'
DATE_PATTERN = re.compile(
    rf'(?<!\d)(?:\d{{4}}-\d{{2}}-\d{{2}}|\b{_MONTH}\s+{_DAY},?\s+\d{{4}}|\b{_DAY}\s+{_MONTH},?\s+\d{{4}})(?!\d)', re.I
)
_MONTHS = {name: i for i, name in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1)}


def parse_date(text):
    """Return exactly one calendar-valid, explicitly year-qualified date."""
    matches = list(DATE_PATTERN.finditer(text or ''))
    if len(matches) != 1:
        return None
    value = matches[0].group()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return calendar_date.fromisoformat(value).isoformat()
        value = re.sub(r'(?<=\d)(st|nd|rd|th)\b', '', value, flags=re.I)
        parts = value.replace(',', '').replace('.', '').split()
        if parts[0].isdigit():
            day, month, year = parts
        else:
            month, day, year = parts
        return calendar_date(int(year), _MONTHS[month[:3].lower()], int(day)).isoformat()
    except (ValueError, KeyError):
        return None


# Match complete offset tokens before finding clocks: 05:30 in UTC+05:30 is
# an offset, never a second clock. A malformed offset must not degrade to UTC.
_ZONE = re.compile(
    r'\b(?:UTC|GMT)(?:\s*[+\-−]\s*\d{1,2}(?::?\d{2})?)?'
    r'|(?<![A-Za-z])[+\-−]\d{2}:\d{2}'
    r'|\b(?:AoE|Anywhere\s+on\s+Earth|PST|PDT)\b'
    r'|(?<=\d)Z\b', re.I
)
_CLOCK = re.compile(r'(?<!\d)(\d{1,2})(?::(\d{2}))(?::(\d{2}))?\s*(AM|PM)?\b|(?<!\w)(\d{1,2})\s*(AM|PM)\b', re.I)


def _offset(token):
    token = re.sub(r'\s+', '', token.upper()).replace('−', '-')
    if token in {'AOE', 'ANYWHEREONEARTH'}:
        return '-12:00'
    if token in {'PST', 'PDT'}:
        return '-08:00' if token == 'PST' else '-07:00'
    if token in {'UTC', 'GMT', 'Z'}:
        return '+00:00'
    token = re.sub(r'^(UTC|GMT)', '', token)
    match = re.fullmatch(r'([+-])(\d{1,2})(?::(\d{2}))?', token)
    if not match:
        match = re.fullmatch(r'([+-])(\d{2})(\d{2})', token)
    if not match:
        return None
    sign, hours, minutes = match.groups()
    hours, minutes = int(hours), int(minutes or 0)
    if hours > 14 or minutes > 59 or (hours == 14 and minutes):
        return None
    return f'{sign}{hours:02}:{minutes:02}'


def parse_timestamp(block, date, aoe=False):
    """Return a timestamp only when one clock and an explicit zone agree.

    AoE alone explicitly denotes the end of that calendar day. Other zones
    require a clock. Regional abbreviations such as PT remain review-only.
    """
    block = re.sub(r'\b(\d{1,2})\.(\d{2})\s*(?=[ap]\.?m)', r'\1:\2 ', block, flags=re.I)
    block = re.sub(r'\b((?:UTC|GMT)\s*[+-]\s*\d{1,2})h\b', r'\1', block, flags=re.I)
    block = re.sub(r'\b([ap])\s*\.\s*m\s*\.', lambda m: m[1] + 'M', block, flags=re.I)
    try:
        calendar_date.fromisoformat(date)
    except (ValueError, TypeError):
        return None
    if re.search(r'\b(?:PT|ET|CT|EST|EDT|CST|CDT|CET|CEST|BST|IST|JST)\b', block, re.I):
        return None
    zones = list(_ZONE.finditer(block))
    offsets = [_offset(match.group()) for match in zones]
    if aoe:
        offsets.append('-12:00')
    if not offsets or None in offsets or len(set(offsets)) != 1:
        return None
    # Prevent a valid prefix of a malformed zone/time from being accepted.
    for match in zones:
        if re.match(r'[\w:]|\.\d|\s*[+−-]', block[match.end():]):
            return None
    masked = list(block)
    for match in zones:
        masked[match.start():match.end()] = ' ' * (match.end() - match.start())
    clocks = list(_CLOCK.finditer(''.join(masked)))
    if not clocks:
        return date + 'T23:59:59-12:00' if offsets[0] == '-12:00' and (aoe or re.search(r'\bAoE\b|Anywhere\s+on\s+Earth', block, re.I)) else None
    if len(clocks) != 1:
        return None
    match = clocks[0]
    if re.match(r'[:\d]|\.\d', ''.join(masked)[match.end():]):
        return None
    hour, minute, second, period, bare_hour, bare_period = match.groups()
    hour, minute, second = int(hour or bare_hour), int(minute or 0), int(second or 0)
    period = period or bare_period
    if period:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if period.upper() == 'PM' else 0)
    value = f'{date}T{hour:02}:{minute:02}:{second:02}{offsets[0]}'
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return None
    return value
