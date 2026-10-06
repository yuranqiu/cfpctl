import sys; sys.path.insert(0, '/app')
from scripts.official_adapters import extract_adapter, _SITES
for slug in _SITES:
    host, path, _ = _SITES[slug]
    url = 'https://' + host + path + '/'
    result = extract_adapter('<p>Updated website</p>', url, {'slug': slug, 'cycles': []})
    print(f'{slug}: {type(result).__name__} -> {result}')
