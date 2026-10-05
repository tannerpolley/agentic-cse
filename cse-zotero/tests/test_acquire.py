"""Acquisition regressions: route boundaries, hard stops and persistent limits."""
import json
from pathlib import Path

import pytest

from zotero_companion import acquire as mod
from zotero_companion.acquire import request as http_request
from zotero_companion.plugin_client import PluginClientError


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    real_safety = mod.Safety
    monkeypatch.setattr(mod, "Safety", lambda: real_safety(tmp_path / 'state.json'))
    monkeypatch.setattr(mod, "require_vpn", lambda: None)
    monkeypatch.setattr(mod, "CONFIG", tmp_path)
    calls = []
    class API:
        def items(self, **kwargs):
            return []
        def get(self, path):
            if path.endswith('children'):
                return [{'key': 'PDFKEY', 'data': {'contentType': 'application/pdf'}}] if current['has_pdf'] else []
            return {'data': {'DOI': current['doi']}}
    class Plugin:
        def __init__(self, **kwargs):
            pass
        def _request(self, path, **kwargs):
            calls.append((path, kwargs['payload']['mode']))
            if path.endswith('metadata'):
                return {'metadata': {'title': 'Regression paper', 'DOI': current['doi']}, 'item_key': 'PARENT', 'collection_key': 'COLL'}
            current['has_pdf'] = True
            return {'attachment_key': 'PDFKEY'}
    def request(url, **kwargs):
        calls.append((url, kwargs.get('route')))
        if 'crossref' in url:
            return json.dumps({'message': {'member': current['member']}}).encode()
        if 'unpaywall' in url:
            return b'{"oa_locations":[]}'
        if 'idconv' in url:
            return b'{"records":[]}'
        return b'%PDF-1.7 test'
    current = {'doi': '', 'member': '', 'has_pdf': True}
    monkeypatch.setattr(mod, 'ZoteroLocalAPI', API)
    monkeypatch.setattr(mod, 'ZoteroPluginClient', Plugin)
    monkeypatch.setattr(mod, 'request', request)
    def forbidden(*args):
        pytest.fail('Restricted publisher reached the browser')
    monkeypatch.setattr('zotero_companion.agent_browser.browser_pdf', forbidden)
    return current, calls, tmp_path


@pytest.mark.parametrize('doi,member,name,tokenfile', [
    ('10.1016/test', 78, 'elsevier', 'elsevier-api-key'),
    ('10.1002/test', 311, 'wiley', 'wiley-tdm-token'),
    ('10.1021/test', 316, 'acs', None),
    ('10.5555/test', 78, 'elsevier', 'elsevier-api-key'),
])
def test_api_only_publishers_never_reach_browser(runtime, doi, member, name, tokenfile):
    current, calls, root = runtime
    current.update(doi=doi, member=member)
    if tokenfile:
        path = root / tokenfile
        path.write_text('secret-test-token\n')
        path.chmod(0o600)
    result = mod.acquire(doi)
    assert result['publisher'] == name
    assert result['ok'] == bool(tokenfile)
    assert result['route'] == (name + '-api' if tokenfile else None)
    assert result['attachment_key'] == ('PDFKEY' if tokenfile else None)
    forced = mod.acquire(doi, route='browser')
    assert not forced['ok'] and 'API-only' in forced['stop_reason']
    assert all('secret-test-token' not in str(call) for call in calls)


def test_429_and_challenge_stop_and_survive_restart(tmp_path):
    path = tmp_path / 'state.json'
    for status, body in [(429, b''), (200, b'<title>Just a moment...</title>'), (200, b'<script>const POW_CHALLENGE="test";</script>')]:
        with mod.Safety(path) as state:
            with pytest.raises(mod.AcquireStop):
                state.response('elsevier', status, body, host='API.ELSEVIER.COM.')
        with mod.Safety(path) as state:
            with pytest.raises(mod.AcquireStop, match='cooldown'):
                state.available('elsevier')
            with pytest.raises(mod.AcquireStop, match='cooldown'):
                state.before('unclassified', 'https://api.elsevier.com/file', 'api', api=True)
            assert state.data['elsevier']['cooldown_until'] == state.data['api.elsevier.com']['cooldown_until']
    with mod.Safety(path) as state:
        with pytest.raises(mod.AcquireStop, match='Non-PDF'):
            state.response('other', 200, b'<html>not a pdf</html>', is_pdf=True)
    assert json.loads(path.read_text())['other']['stop_reason'].startswith('Non-PDF')


def test_pacing_daily_cap_and_lock_persist(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, 'require_vpn', lambda: None)
    clock = [1000000.0]
    monkeypatch.setattr(mod.time, 'time', lambda: clock[0])
    monkeypatch.setattr(mod.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    path = tmp_path / 'state.json'
    with mod.Safety(path) as state:
        state.before('plos', 'https://JOURNALS.PLOS.ORG./article', 'browser')
        with pytest.raises(mod.AcquireStop, match='Another acquisition'):
            with mod.Safety(path):
                pass
    with mod.Safety(path) as state:
        state.before('plos', 'https://journals.plos.org/pdf', 'browser')
        assert clock[0] == 1000060
        state.data['plos']['count'] = 25
        state.save()
    with mod.Safety(path) as state:
        with pytest.raises(mod.AcquireStop, match='daily'):
            state.before('plos', 'https://journals.plos.org/another', 'browser')
        state.before('wiley', 'https://api.wiley.com/article', 'api', api=True)
        state.before('wiley', 'https://api.wiley.com/article', 'api', api=True)
        assert clock[0] == 1000070
        with pytest.raises(mod.AcquireStop, match='API-only'):
            state.before('elsevier', 'https://www.sciencedirect.com/pdf', 'oa')


def test_oa_pdf_stops_further_requests(runtime, monkeypatch):
    current, calls, root = runtime
    current.update(doi='10.1371/test', member=340)
    original = mod.request
    def request(url, **kwargs):
        if 'unpaywall' in url:
            return b'{"best_oa_location":{"url_for_pdf":"https://repository.example/paper.pdf"},"oa_locations":[]}'
        return original(url, **kwargs)
    monkeypatch.setattr(mod, 'request', request)
    result = mod.acquire(current['doi'])
    assert result['ok'] and result['verified'] and result['route'] == 'unpaywall'


@pytest.mark.parametrize('source', ['location', 'landing', 'converter', 'outside-oa'])
def test_pmc_cloud_selects_declared_main_pdf_and_preserves_cooldowns(runtime, monkeypatch, source):
    import base64
    import io
    from urllib.parse import parse_qs, urlsplit
    current, calls, root = runtime
    current.update(doi='10.1371/test', member=340, has_pdf=False)
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda self, **kwargs: [
        {'key': 'EXISTING', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    clock = [1000000.0]
    monkeypatch.setattr(mod.time, 'time', lambda: clock[0])
    monkeypatch.setattr(mod.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    cooldowns = {} if source == 'outside-oa' else {'crossref-340': {'cooldown_until': clock[0] + 86400}}
    if source != 'converter':
        cooldowns['pmc.ncbi.nlm.nih.gov'] = {'cooldown_until': clock[0] + 86400}
    (root / 'state.json').write_text(json.dumps(cooldowns))
    main = b'%PDF-1.7 main article'
    location = {'host_type': 'repository', 'url_for_pdf': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/paper.pdf'}
    if source == 'landing':
        location = {'host_type': 'repository', 'url_for_landing_page': 'https://www.ncbi.nlm.nih.gov/pmc/articles/123/'}
    urls, times = [], []
    class Opener:
        def open(self, request, **kwargs):
            url = request.full_url
            urls.append(url)
            times.append(clock[0])
            assert 'cse-zotero' in request.get_header('User-agent') and mod.EMAIL in request.get_header('User-agent')
            if 'crossref.org' in url:
                body = json.dumps({'message': {'member': 340}}).encode()
            elif 'unpaywall.org' in url:
                locations = [] if source == 'converter' else [location]
                if source == 'outside-oa':
                    locations.append({'url_for_pdf': 'https://repository.example/alternative.pdf'})
                body = json.dumps({'oa_locations': locations}).encode()
            elif 'idconv' in url:
                params = parse_qs(urlsplit(url).query)
                assert params['ids'] == [current['doi']] and params['tool'] == ['cse-zotero'] and params['email'] == [mod.EMAIL]
                body = json.dumps({'records': [{'doi': current['doi'], 'pmcid': 'PMC123'}]}).encode()
            elif 'list-type=2' in url:
                assert parse_qs(urlsplit(url).query)['prefix'] == ['metadata/PMC123.']
                body = b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>false</IsTruncated><Contents><Key>metadata/PMC123.2.json</Key></Contents></ListBucketResult>'
            elif url.endswith('.json'):
                body = json.dumps({'pmcid': 'PMC123', 'doi': current['doi'], 'is_pmc_openaccess': source != 'outside-oa',
                                   'pdf_url': 's3://pmc-oa-opendata/PMC123.2/article.pdf?md5=abc',
                                   'media_urls': ['s3://pmc-oa-opendata/PMC123.2/supplement.pdf']}).encode()
            else:
                assert url in {mod.PMC_CLOUD + '/PMC123.2/article.pdf?md5=abc', 'https://repository.example/alternative.pdf'}
                body = main
            response = io.BytesIO(body)
            response.code, response.headers = 200, {}
            response.geturl = lambda: url
            return response
    monkeypatch.setattr(mod, 'request', http_request)
    monkeypatch.setattr(mod, 'build_opener', lambda *args: Opener())
    original_plugin = mod.ZoteroPluginClient._request
    def attach(self, path, **kwargs):
        assert path.endswith('attachment') and kwargs['payload']['item_key'] == 'EXISTING'
        assert base64.b64decode(kwargs['payload']['pdf_base64']) == main
        return original_plugin(self, path, **kwargs)
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', attach)
    result = mod.acquire(current['doi'])
    assert result['ok'] and result['verified'] and result['attachment_key'] == 'PDFKEY'
    assert result['route'] == ('unpaywall' if source == 'outside-oa' else 'pmc-cloud')
    assert all(b - a >= 1 for a, b in zip(times, times[1:]))
    state = json.loads((root / 'state.json').read_text())
    assert all(state[host]['cooldown_until'] == entry['cooldown_until'] for host, entry in cooldowns.items())
    assert not any('/pdf/' in url or 'supplement.pdf' in url for url in urls)
    with mod.Safety() as safety:
        with pytest.raises(mod.AcquireStop, match='official PMC Cloud'):
            safety.check_url(location.get('url_for_pdf') or 'https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/paper.pdf')


@pytest.mark.parametrize('has_pdf', [True, False])
@pytest.mark.parametrize('matched_by', ['doi', 'title'])
def test_existing_parent_returns_pdf_or_resumes_routes(runtime, monkeypatch, has_pdf, matched_by):
    current, calls, _ = runtime
    current.update(doi='10.1371/test', member=340, has_pdf=has_pdf)
    if matched_by == 'doi':
        monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda self, **kwargs: [
            {'key': 'EXISTING', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    original_plugin = mod.ZoteroPluginClient._request
    def plugin(self, path, **kwargs):
        result = original_plugin(self, path, **kwargs)
        if path.endswith('metadata'):
            result.update(existing=True, item_key='EXISTING')
        else:
            assert kwargs['payload']['item_key'] == 'EXISTING'
        return result
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', plugin)
    original_request = mod.request
    def request(url, **kwargs):
        if 'unpaywall' in url:
            calls.append((url, kwargs.get('route')))
            return b'{"best_oa_location":{"url_for_pdf":"https://repository.example/paper.pdf"}}'
        return original_request(url, **kwargs)
    monkeypatch.setattr(mod, 'request', request)
    result = mod.acquire(current['doi'])
    assert result['ok'] and result['verified'] and result['item_key'] == 'EXISTING'
    assert result['attachment_key'] == 'PDFKEY'
    assert result['route'] == ('existing' if has_pdf else 'unpaywall')
    assert bool(any(path.endswith('attachment') for path, _ in calls)) == (not has_pdf)
    assert bool(any('unpaywall' in path for path, _ in calls)) == (not has_pdf)
    assert bool(any(path.endswith('metadata') for path, _ in calls)) == (matched_by == 'title')


def test_metadata_busy_returns_a_stop(runtime, monkeypatch):
    current, _, _ = runtime
    current.update(doi='10.1371/test', member=340)
    def busy(*args, **kwargs):
        raise PluginClientError('HTTP 409: metadata_acquisition_busy')
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', busy)
    result = mod.acquire(current['doi'])
    assert not result['ok'] and 'busy' in result['stop_reason']
    assert result['item_key'] is None and result['attachment_key'] is None


@pytest.mark.parametrize('status,body', [(429, b''), (403, b''), (403, b'<html>CAPTCHA</html>'), (200, b'<html>CAPTCHA</html>'), (200, b'not a PDF')])
def test_api_hard_stop_cannot_fall_through(runtime, monkeypatch, status, body):
    current, calls, root = runtime
    current.update(doi='10.1016/test', member=78)
    path = root / 'elsevier-api-key'
    path.write_text('secret-test-token')
    path.chmod(0o600)
    original = mod.request
    def response(url, **kwargs):
        if 'api.elsevier' in url:
            kwargs['safety'].response('elsevier', status, body, is_pdf=True)
        return original(url, **kwargs)
    monkeypatch.setattr(mod, 'request', response)
    result = mod.acquire(current['doi'])
    assert not result['ok'] and result['item_key'] == 'PARENT' and not result['attachment_key']
    assert not any(path.endswith('attachment') for path, _ in calls)
    state = json.loads((root / 'state.json').read_text())
    assert bool(state['elsevier'].get('cooldown_until')) == (status == 429 or b'CAPTCHA' in body)


@pytest.mark.parametrize("value,doi", [
    ("https://onlinelibrary.wiley.com/doi/10.1002/test/full", "10.1002/test"),
    ("https://onlinelibrary.wiley.com/doi/pdf/10.1002/test", "10.1002/test"),
    ("https://journals.plos.org/article?id=10.1371/test&tracking=1", "10.1371/test"),
    ("https://doi.org/10.5555/test/full", "10.5555/test/full"),
    ("10.5555/test/full", "10.5555/test/full"),
])
def test_article_url_doi_boundary(value, doi):
    assert mod.identifier(value) == doi


@pytest.mark.parametrize("url,doi,member", [
    ("https://www.sciencedirect.com/science/article/doi/10.1016/test", "10.1016/test", 78),
    ("https://onlinelibrary.wiley.com/doi/10.1002/test/full", "10.1002/test", 311),
    ("https://pubs.acs.org/doi/10.1021/test", "10.1021/test", 316),
])
def test_restricted_article_url_uses_only_identifier_translation(runtime, monkeypatch, url, doi, member):
    current, calls, _ = runtime
    current.update(doi=doi, member=member)
    original = mod.ZoteroPluginClient._request
    def translated(self, path, **kwargs):
        if path.endswith("metadata"):
            assert kwargs["payload"]["identifier"] == doi
        return original(self, path, **kwargs)
    monkeypatch.setattr(mod.ZoteroPluginClient, "_request", translated)
    result = mod.acquire(url)
    assert result["item_key"] == "PARENT" and result["doi"] == doi
    assert not any(path == url for path, _ in calls)


def test_input_credentials_never_reach_json_or_network(runtime):
    _, calls, _ = runtime
    result = mod.acquire("https://user:private-password@example.org/article")
    assert not result["ok"] and result["handoff_url"] is None
    assert "private-password" not in json.dumps(result)
    assert not calls


@pytest.mark.parametrize("doi,member", [("10.1016/test", 78), ("10.1002/test", 311), ("10.1021/test", 316)])
def test_restricted_oa_requires_explicit_repository(runtime, monkeypatch, doi, member):
    current, calls, root = runtime
    current.update(doi=doi, member=member)
    original = mod.request
    def response(url, **kwargs):
        if "unpaywall" in url:
            return json.dumps({"oa_locations": [
                {"url_for_pdf": "https://alternate-publisher.example/paper.pdf", "host_type": "publisher"},
                {"url_for_pdf": "https://unverified.example/paper.pdf"},
                {"url_for_pdf": "https://repository.example/paper.pdf", "host_type": "repository"},
            ]}).encode()
        return original(url, **kwargs)
    monkeypatch.setattr(mod, "request", response)
    result = mod.acquire(doi)
    assert result["ok"] and result["route"] == "unpaywall"
    fetched = [url for url, route in calls if route is None and url.startswith("https:")]
    assert "https://repository.example/paper.pdf" in fetched
    assert not any("alternate-publisher" in url or "unverified" in url for url in fetched)


def test_native_identifier_discovered_doi_still_blocks_browser(runtime):
    current, calls, _ = runtime
    current.update(doi="10.1016/test", member=78)
    result = mod.acquire("PMID:12345678", route="browser")
    assert not result["ok"] and "API-only" in result["stop_reason"]
    assert result["item_key"] == "PARENT" and result["doi"] == current["doi"]
    assert not result["attachment_key"]


def test_public_api_pacing_and_credential_redirect(monkeypatch, tmp_path):
    import io
    clock = [1000000.0]
    monkeypatch.setattr(mod.time, "time", lambda: clock[0])
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    urls = []
    class Opener:
        def open(self, request, **kwargs):
            urls.append(request.full_url)
            response = io.BytesIO(b"{}")
            response.code = 302 if "elsevier" in request.full_url else 200
            response.headers = {"Location": "https://other.example/file.pdf"}
            response.geturl = lambda: request.full_url
            return response
    monkeypatch.setattr(mod, "build_opener", lambda *args: Opener())
    def vpn():
        pytest.fail("Public metadata request incorrectly requires the VPN")
    monkeypatch.setattr(mod, "require_vpn", vpn)
    with mod.Safety(tmp_path / "state.json") as safety:
        mod.request("https://api.crossref.org/works/test", safety=safety)
        mod.request("https://api.unpaywall.org/v2/test", safety=safety)
        assert clock[0] == 1000001.0
        monkeypatch.setattr(mod, "require_vpn", lambda: None)
        with pytest.raises(mod.AcquireStop, match="credential redirect"):
            mod.request("https://api.elsevier.com/content/article/doi/test", safety=safety,
                        pub="elsevier", route="api", headers={"X-ELS-APIKey": "private-token"})
    assert urls[-1].startswith("https://api.elsevier.com/") and len(urls) == 3


def test_redirect_final_url_trailing_dot_and_cdn_hosts_are_refused(monkeypatch, tmp_path):
    import io
    monkeypatch.setattr(mod, 'require_vpn', lambda: None)
    for target in ('https://CDN.SCIENCEDIRECTASSETS.COM./paper.pdf', 'https://www.thelancet.com/paper.pdf',
                   'https://ＰＵＢＳ.ＡＣＳ.org./paper.pdf', 'https://onlinelibrary.wiley.com./paper.pdf'):
        for redirected in (True, False):
            urls = []
            class Opener:
                def open(self, request, **kwargs):
                    urls.append(request.full_url)
                    response = io.BytesIO(b'')
                    response.code = 302 if redirected else 200
                    response.headers = {'Location': target}
                    response.geturl = lambda: request.full_url if redirected else target
                    return response
            monkeypatch.setattr(mod, 'build_opener', lambda *args: Opener())
            with mod.Safety(tmp_path / 'state.json') as safety:
                with pytest.raises(mod.AcquireStop, match='API-only'):
                    mod.request('https://repository.example/paper.pdf', safety=safety, pub='unknown', is_pdf=True)
            assert urls == ['https://repository.example/paper.pdf']


@pytest.mark.parametrize("outcome", ["active", "activated", "failed", "not_active"])
def test_vpn_activation_is_bounded_and_rechecked(monkeypatch, outcome):
    from types import SimpleNamespace
    commands = []
    def run(command, **kwargs):
        commands.append((command, kwargs["timeout"]))
        if "up" in command:
            if outcome == "failed":
                raise mod.subprocess.TimeoutExpired(command, kwargs["timeout"])
            return SimpleNamespace(stdout="")
        up_done = any("up" in cmd for cmd, _ in commands)
        return SimpleNamespace(stdout="CAEDM IKEv2 VPN\n" if outcome == "active" or (up_done and outcome == "activated") else "")
    monkeypatch.setattr(mod.subprocess, "run", run)
    if outcome in {"failed", "not_active"}:
        with pytest.raises(mod.AcquireStop):
            mod.require_vpn()
    else:
        mod.require_vpn()
    assert len(commands) == (1 if outcome == "active" else 2 if outcome == "failed" else 3)
    assert all(timeout in {5, 30} for _, timeout in commands)
    assert not any("down" in cmd or "modify" in cmd for cmd, _ in commands)



def test_non_doi_parent_identity_is_verified(runtime, monkeypatch):
    monkeypatch.setattr("zotero_companion.agent_browser.browser_pdf", lambda *args: b"%PDF-1.7")
    original = mod.ZoteroPluginClient._request
    def metadata(self, path, **kwargs):
        result = original(self, path, **kwargs)
        if path.endswith("metadata"):
            result["metadata"]["url"] = "https://arxiv.org/abs/1234.5678"
        return result
    monkeypatch.setattr(mod.ZoteroPluginClient, "_request", metadata)
    result = mod.acquire("arXiv:1234.5678")
    assert not result["ok"] and "parent title" in result["stop_reason"]
    assert result["attachment_key"] == "PDFKEY"



def test_native_metadata_operation_reserves_api_slot(runtime, monkeypatch):
    _, _, path = runtime
    clock = [1000000.0]
    monkeypatch.setattr(mod.time, "time", lambda: clock[0])
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    result = mod.acquire("arXiv:1234.5678", dry_run=True)
    assert result["ok"]
    assert json.loads((path / "state.json").read_text())["last_api"] == clock[0]
    result = mod.acquire("PMID:12345678", dry_run=True)
    assert result["ok"] and clock[0] == 1000001.0
