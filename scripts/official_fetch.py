"""Bounded HTTPS fetching with optional replayable page snapshots."""
import hashlib
import json
import time
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class HTTPSRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('official page redirected to non-HTTPS URL')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(str):
    def __new__(cls, text, url):
        obj = super().__new__(cls, text)
        obj.url = url
        return obj


class WebsiteFetcher:
    def __init__(self, timeout=20, cache_dir=None, offline=False):
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.offline = offline
        if offline and not self.cache_dir:
            raise ValueError('offline mode requires a cache directory')
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, url):
        if urlsplit(url).scheme != 'https':
            raise ValueError('HTTPS official URL required')
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache_dir / (key + '.json') if self.cache_dir else None
        if path and path.exists():
            try:
                cached = json.loads(path.read_text(encoding='utf-8'))
                if cached['url'] != url or (not cached.get('error') and
                                           urlsplit(cached['resolved_url']).scheme != 'https'):
                    raise ValueError('invalid page snapshot identity')
                fresh = time.time() - cached['fetched_at'] < (300 if cached.get('error') else 86400)
            except (KeyError, ValueError, TypeError) as exc:
                if self.offline:
                    raise OSError('invalid offline snapshot: ' + url) from exc
                cached, fresh = {}, False
            if self.offline or fresh:
                if cached.get('error'):
                    raise OSError(cached['error'])
                return Page(cached['html'], cached['resolved_url'])
        if self.offline:
            raise OSError('page not available in offline cache: ' + url)
        record = {'url': url, 'fetched_at': time.time()}
        for attempt in range(2):
            try:
                request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; cfpctl/1.0; official conference date checker)'})
                with build_opener(HTTPSRedirectHandler()).open(request, timeout=self.timeout) as response:
                    if urlsplit(response.url).scheme != 'https':
                        raise ValueError('official page redirected to non-HTTPS URL')
                    raw = response.read(4 * 1024 * 1024 + 1)
                    if len(raw) > 4 * 1024 * 1024:
                        raise ValueError('website exceeds 4 MiB limit')
                    record.update(html=raw.decode(response.headers.get_content_charset() or 'utf-8'),
                                  resolved_url=response.url, status=response.status)
                break
            except Exception as exc:
                retry = ((isinstance(exc, HTTPError) and exc.code in (429, 500, 502, 503, 504))
                         or (not isinstance(exc, HTTPError) and isinstance(exc, (URLError, TimeoutError, ConnectionError))))
                if attempt == 0 and retry:
                    time.sleep(1)
                    continue
                record['error'] = f'{url}: {exc}'
                break
        if path:
            # Concurrent conferences can share a page; readers must see a complete snapshot.
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump(record, stream, ensure_ascii=False)
                temporary.replace(path)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        if record.get('error'):
            raise OSError(record['error'])
        return Page(record['html'], record['resolved_url'])
