import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request

from scripts.official_fetch import WebsiteFetcher, HTTPSRedirectHandler


class FetchTests(unittest.TestCase):
    url = 'https://example.org/2027/'

    def response(self, content=b'<title>Example 2027</title>'):
        response = Mock(url=self.url + 'cfp', status=200)
        response.read.return_value = content
        response.headers.get_content_charset.return_value = 'utf-8'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    @patch('scripts.official_fetch.build_opener')
    def test_snapshot_replays_redirect_without_network(self, opener):
        opener.return_value.open.return_value = self.response()
        with tempfile.TemporaryDirectory() as directory:
            page = WebsiteFetcher(cache_dir=directory)(self.url)
            opener.return_value.open.assert_called_once()
            opener.reset_mock()
            replay = WebsiteFetcher(cache_dir=directory, offline=True)(self.url)
            self.assertEqual((str(page), page.url), (str(replay), replay.url))
            opener.assert_not_called()

    @patch('scripts.official_fetch.time.sleep')
    @patch('scripts.official_fetch.build_opener')
    def test_transient_error_has_one_retry(self, opener, sleep):
        opener.return_value.open.side_effect = [HTTPError(self.url, 503, 'busy', {}, None), self.response()]
        self.assertIn('Example', WebsiteFetcher()(self.url))
        self.assertEqual(opener.return_value.open.call_count, 2)

    @patch('scripts.official_fetch.build_opener')
    def test_forbidden_is_not_retried_and_failure_replays(self, opener):
        opener.return_value.open.side_effect = HTTPError(self.url, 403, 'forbidden', {}, None)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(OSError, '403'):
                WebsiteFetcher(cache_dir=directory)(self.url)
            self.assertEqual(opener.return_value.open.call_count, 1)
            opener.reset_mock()
            with self.assertRaisesRegex(OSError, '403'):
                WebsiteFetcher(cache_dir=directory, offline=True)(self.url)
            opener.assert_not_called()

    @patch('scripts.official_fetch.build_opener')
    def test_size_limit_and_http_rejected(self, opener):
        opener.return_value.open.return_value = self.response(b'x' * (4 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(OSError, '4 MiB'):
            WebsiteFetcher()(self.url)
        with self.assertRaises(ValueError):
            WebsiteFetcher()('http://example.org')
        with self.assertRaises(ValueError):
            HTTPSRedirectHandler().redirect_request(Request(self.url), None, 302, '', {}, 'http://example.org')

    @patch('scripts.official_fetch.build_opener')
    def test_missing_and_corrupt_offline_cache_never_fetch(self, opener):
        with tempfile.TemporaryDirectory() as directory:
            fetch = WebsiteFetcher(cache_dir=directory, offline=True)
            with self.assertRaisesRegex(OSError, 'not available'):
                fetch(self.url)
            path = Path(directory) / (hashlib.sha256(self.url.encode()).hexdigest() + '.json')
            path.write_text(json.dumps({'url': 'https://wrong.org'}))
            with self.assertRaisesRegex(OSError, 'invalid offline'):
                fetch(self.url)
            opener.assert_not_called()
