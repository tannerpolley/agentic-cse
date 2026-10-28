"""Acquisition regressions: route boundaries, hard stops and persistent limits."""
import json
from pathlib import Path

import pytest

from zotero_companion import acquire as mod
from zotero_companion.acquire import request as http_request
from zotero_companion.plugin_client import PluginClientError


def fixture_pdf(pages=4):
    """A small valid PDF with a real page tree and cross-reference table."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Count {pages} /Kids [".encode() +
               b" ".join(f"{i + 3} 0 R".encode() for i in range(pages)) + b"] >>"]
    objects += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> >>"] * pages
    body = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(body)
    body += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return body + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    real_safety = mod.Safety
    monkeypatch.setattr(mod, "Safety", lambda: real_safety(tmp_path / 'state.json'))
    monkeypatch.setattr(mod, "require_vpn", lambda: None)
    monkeypatch.setattr(mod, "CONFIG", tmp_path)
    calls = []
    pdf_path = tmp_path / 'retained.pdf'
    pdf_path.write_bytes(fixture_pdf())
    class API:
        def items(self, **kwargs):
            return []
        def get_text(self, path):
            return pdf_path.as_uri()
        def get(self, path):
            if path.endswith('children'):
                return [{'key': 'PDFKEY', 'data': {'contentType': 'application/pdf'}}] if current['has_pdf'] else []
            return {'data': {'DOI': current['doi']}}
    class Plugin:
        def __init__(self, **kwargs):
            pass
        def _request(self, path, **kwargs):
            if path.endswith('acquire-job'):
                return {}
            calls.append((path, kwargs['payload']['mode']))
            if path.endswith('metadata'):
                if kwargs['payload']['mode']=='apply':
                    with pytest.raises(mod.AcquireStop, match='Another acquisition'):
                        with mod.Safety():
                            pass
                return {'metadata': {'title': 'Regression paper', 'DOI': current['doi']}, 'item_key': 'PARENT', 'collection_key': 'COLL'}
            if path.endswith('connector'):
                if kwargs['payload']['mode']=='dry-run':
                    return {'collection_key': 'COLL'}
                return {'item_key': kwargs['payload'].get('existing_key') or 'PARENT', 'attachment_key': 'PDFKEY', 'metadata': {'DOI': current['doi'], 'title': 'Regression paper'}, 'collection_key': 'COLL'}
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
        return fixture_pdf()
    current = {'doi': '', 'member': '', 'has_pdf': True}
    monkeypatch.setattr(mod, 'ZoteroLocalAPI', API)
    monkeypatch.setattr(mod, 'ZoteroPluginClient', Plugin)
    monkeypatch.setattr(mod, 'request', request)
    def connector(*args, **kwargs):
        calls.append(('connector-visit', None))
        current['has_pdf'] = True
        return {'session_id': 'SESSION'}
    monkeypatch.setattr('zotero_companion.connector_job.connector_save', connector)
    return current, calls, tmp_path


@pytest.mark.parametrize('doi,member,name,tokenfile', [
    ('10.1016/test', 78, 'elsevier', 'elsevier-api-key'),
    ('10.1002/test', 311, 'wiley', 'wiley-tdm-token'),
    ('10.1021/test', 316, 'acs', None),
    ('10.5555/test', 78, 'elsevier', 'elsevier-api-key'),
])
def test_api_precedes_connector_for_all_publishers(runtime, doi, member, name, tokenfile):
    current, calls, root = runtime
    current.update(doi=doi, member=member)
    if tokenfile:
        path = root / tokenfile
        path.write_text('secret-test-token\n')
        path.chmod(0o600)
    result = mod.acquire(doi)
    assert result['publisher'] == name
    assert result['ok']
    assert result['route'] == (name + '-api' if tokenfile else 'connector')
    assert result['attachment_key'] == 'PDFKEY'
    assert ('connector-visit', None) not in calls if tokenfile else ('connector-visit', None) in calls
    forced = mod.acquire(doi, route='browser')
    assert forced['ok'] and forced['route'] == 'connector'
    assert all('secret-test-token' not in str(call) for call in calls)


def test_429_and_challenge_stop_without_a_publisher_hold(tmp_path):
    path = tmp_path / 'state.json'
    for status, body in [(429, b''), (200, b'<title>Just a moment...</title>'), (200, b'<script>const POW_CHALLENGE="test";</script>')]:
        with mod.Safety(path) as state:
            with pytest.raises(mod.AcquireStop):
                state.response('elsevier', status, body, host='API.ELSEVIER.COM.')
        saved = json.loads(path.read_text())
        assert saved['elsevier']['stop_reason'] and saved['api.elsevier.com']['stop_reason']
        assert not any('cooldown_until' in entry for entry in saved.values() if isinstance(entry, dict))
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
        with pytest.raises(mod.AcquireStop, match='Connector or official API'):
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
def test_pmc_cloud_selects_declared_main_pdf(runtime, monkeypatch, source):
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
    main = fixture_pdf()
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
        if path.endswith('acquire-job'):
            return original_plugin(self, path, **kwargs)
        assert path.endswith('attachment') and kwargs['payload']['item_key'] == 'EXISTING'
        assert base64.b64decode(kwargs['payload']['pdf_base64']) == main
        return original_plugin(self, path, **kwargs)
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', attach)
    result = mod.acquire(current['doi'])
    assert result['ok'] and result['verified'] and result['attachment_key'] == 'PDFKEY'
    assert result['route'] == ('unpaywall' if source == 'outside-oa' else 'pmc-cloud')
    assert all(b - a >= 1 for a, b in zip(times, times[1:]))
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
        if path.endswith('acquire-job'):
            return result
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


@pytest.mark.parametrize('doi,reason', [
    ('10.1021/je960141+', 'native translation failure'),
    ('10.22034/ijche.2024.450400.1526', 'No items returned from any translator; hand off the DOI landing page'),
])
def test_metadata_endpoint_message_reaches_stop_reason(runtime, monkeypatch, doi, reason):
    from io import BytesIO
    from urllib.error import HTTPError
    from zotero_companion import plugin_client

    runtime[0].update(doi=doi)
    payload = json.dumps({'error': 'metadata_acquisition_failed', 'message': reason}).encode()
    def failed_response(request, **kwargs):
        assert json.loads(request.data)['identifier'] == doi
        raise HTTPError(request.full_url, 500, 'Internal Server Error', {}, BytesIO(payload))
    monkeypatch.setattr(plugin_client, 'urlopen', failed_response)
    monkeypatch.setattr(mod, 'ZoteroPluginClient', plugin_client.ZoteroPluginClient)
    result = mod.acquire(doi, dry_run=True)
    assert not result['ok'] and reason in result['stop_reason']
    assert result['handoff_url'] == 'https://doi.org/' + doi
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


def test_native_identifier_discovered_doi_uses_connector(runtime):
    current, calls, _ = runtime
    current.update(doi="10.1016/test", member=78)
    result = mod.acquire("PMID:12345678", route="browser")
    assert result["ok"] and result["route"] == "connector"
    assert result["item_key"] == "PARENT" and result["doi"] == current["doi"]
    assert result["attachment_key"] == "PDFKEY"


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
                with pytest.raises(mod.AcquireStop, match='Connector or official API'):
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
    assert not any(path.endswith('metadata') and mode=='apply' for path, mode in runtime[1])



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



@pytest.mark.parametrize('status,detail,body', [
    (403, 'AUTHENTICATION_ERROR', b'{"error":"Requestor configuration settings insufficient"}'),
    (403, '', b'{"error":"Requestor configuration settings insufficient: private-test-key"}'),
    (429, 'RATE_LIMIT_EXCEEDED', b'quota'),
    (500, 'INTERNAL_SERVER_ERROR', b'server error'),
    (403, 'AUTHENTICATION_ERROR', b'<html>CAPTCHA</html>'),
])
def test_elsevier_configuration_error_falls_through_but_bans_stop(runtime, monkeypatch, status, detail, body):
    import io
    current, calls, root = runtime
    current.update(doi='10.1016/test', member=78, has_pdf=False)
    key = root / 'elsevier-api-key'
    key.write_text('private-test-key')
    key.chmod(0o600)
    class Opener:
        def open(self, req, **kwargs):
            response = io.BytesIO(body)
            response.code, response.headers = status, {'X-ELS-Status': detail}
            response.geturl = lambda: req.full_url
            return response
    monkeypatch.setattr(mod, 'build_opener', lambda *args: Opener())
    original = mod.request
    def response(url, **kwargs):
        return http_request(url, **kwargs) if 'api.elsevier' in url else original(url, **kwargs)
    monkeypatch.setattr(mod, 'request', response)
    result = mod.acquire(current['doi'])
    skipped = status == 403 and b'CAPTCHA' not in body
    assert result['ok'] == skipped
    assert bool(('connector-visit', None) in calls) == skipped
    assert (detail or 'Requestor configuration settings insufficient') in str(result.get('skipped_routes') or result['stop_reason']) or b'CAPTCHA' in body
    assert 'private-test-key' not in json.dumps(result)
    assert not any(path.endswith('metadata') and mode == 'apply' for path, mode in calls) if skipped else result['item_key'] == 'PARENT'


@pytest.mark.parametrize('url', ['https://127.0.0.1/a', 'https://private.internal/a', 'http://public.example/10.1002/test', 'file:///tmp/paper'])
def test_acquire_rejects_non_public_url_before_remote_metadata(runtime, url):
    _, calls, _ = runtime
    result = mod.acquire(url)
    assert not result['ok'] and result['stop_reason']
    assert not calls


def test_connector_partial_save_is_filed_once_then_hands_off(runtime, monkeypatch):
    current, calls, root = runtime
    current.update(doi='10.1016/test', member=78, has_pdf=False)
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda *a, **k: [
        {'key': 'EXISTING', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    monkeypatch.setattr('zotero_companion.connector_job.connector_save', lambda *a, **k: {
        'session_id': 'SESSION', 'url': 'https://doi.org/10.1016/test', 'title': '', 'status': None,
        'stop': {'reason': 'Publisher access challenge: CAPTCHA', 'host': 'WWW.SCIENCEDIRECT.COM.',
                 'url': 'https://www.sciencedirect.com/article/test', 'status': 403}})
    result = mod.acquire(current['doi'])
    assert not result['ok'] and result['item_key'] == 'EXISTING'
    assert result['browser'] == {'url': 'https://www.sciencedirect.com/article/test', 'title': '', 'status': 403}
    assert ('/zotero-companion/acquire-connector', 'apply') in calls
    assert not any(path.endswith('metadata') for path, _ in calls)


def test_connector_empty_session_hands_off_without_losing_existing_key(runtime, monkeypatch):
    current, calls, _ = runtime
    current.update(doi='10.1021/test', member=316, has_pdf=False)
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda *a, **k: [
        {'key': 'EXISTING', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    original = mod.ZoteroPluginClient._request
    def empty_session(self, path, **kwargs):
        if path.endswith('acquire-connector') and kwargs['payload']['mode'] == 'apply':
            return {'handoff': 'Zotero Connector saved no parent item; save with the normal Zotero Connector'}
        return original(self, path, **kwargs)
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', empty_session)
    result = mod.acquire(current['doi'])
    assert not result['ok'] and result['item_key'] == 'EXISTING'
    assert result['attachment_key'] == None
    assert 'saved no parent item' in result['stop_reason'] and '422' not in result['stop_reason']
    assert result['handoff_url'] == 'https://doi.org/' + current['doi']


@pytest.mark.parametrize('pages,article_range,accepted', [(1, '10-19', False), (3, '10-19', False),
    (6, '10-19', True), (1, '123-123', True), (1, 'S10-S10', True), (4, '143279', True)])
def test_pdf_completeness(pages, article_range, accepted):
    body = fixture_pdf(pages)
    if accepted:
        assert mod.pdf_bytes(body, article_range) == body
    else:
        with pytest.raises(mod.IncompletePDF):
            mod.pdf_bytes(body, article_range)


@pytest.mark.parametrize('pages', ['123', 'e123', '143279', ''])
def test_short_paper_without_range_is_uncertain_and_never_replaceable(runtime, monkeypatch, pages):
    current, calls, root = runtime
    current['doi'] = '10.1371/test'
    (root / 'retained.pdf').write_bytes(fixture_pdf(1))
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda *a, **k: [
        {'key': 'PARENT', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    original = mod.request
    monkeypatch.setattr(mod, 'request', lambda url, **kw:
        json.dumps({'message': {'page': pages}}).encode() if 'crossref' in url else original(url, **kw))
    with pytest.raises(mod.UncertainPDF):
        mod.pdf_bytes(fixture_pdf(1), pages)
    for refetch in (False, True):
        result = mod.acquire(current['doi'], refetch=refetch)
        assert not result['ok'] and 'Uncertain' in result['stop_reason']
        assert result['unverified_attachments'][0]['attachment_key'] == 'PDFKEY'
        assert 'replacement' not in result and 'incomplete_attachments' not in result
    assert not any(mode == 'apply' or path == 'connector-visit' for path, mode in calls)


@pytest.mark.parametrize('existing', [True, False])
def test_acquire_uses_zotero_single_page_range_when_crossref_has_article_number(runtime, monkeypatch, existing):
    current, calls, root = runtime
    current['doi'] = '10.1371/test'
    (root / 'retained.pdf').write_bytes(fixture_pdf(1))
    if existing:
        monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda *a, **k: [
            {'key': 'PARENT', 'data': {'itemType': 'journalArticle', 'DOI': current['doi']}}])
    original_get = mod.ZoteroLocalAPI.get
    def get(self, path):
        result = original_get(self, path)
        if not path.endswith('children'):
            result['data']['pages'] = '123-123'
        return result
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'get', get)
    original_plugin = mod.ZoteroPluginClient._request
    def plugin(self, path, **kw):
        result = original_plugin(self, path, **kw)
        if path.endswith('metadata'):
            result['metadata']['pages'] = '123-123'
        return result
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', plugin)
    original = mod.request
    monkeypatch.setattr(mod, 'request', lambda url, **kw:
        b'{"message":{"page":"e123"}}' if 'crossref' in url else original(url, **kw))
    result = mod.acquire(current['doi'])
    assert result['ok'] and result['verified']
    assert result['route'] == ('existing' if existing else 'connector')
    assert 'replacement' not in result


@pytest.mark.parametrize('route', ['unpaywall', 'pmc-cloud', 'elsevier-api', 'wiley-api', 'connector'])
def test_preview_falls_through_or_hands_off(runtime, monkeypatch, route):
    current, calls, root = runtime
    current.update(doi='10.1016/test' if route == 'elsevier-api' else '10.1002/test' if route == 'wiley-api' else '10.1371/test')
    original = mod.request
    def request(url, **kwargs):
        if 'crossref' in url:
            return b'{"message":{"page":"10-19"}}'
        if 'unpaywall' in url and route == 'unpaywall':
            return b'{"oa_locations":[{"url_for_pdf":"https://repository.example/preview.pdf"}]}'
        if 'preview.pdf' in url or 'api.elsevier' in url or 'api.wiley' in url:
            return fixture_pdf(1)
        return original(url, **kwargs)
    monkeypatch.setattr(mod, 'request', request)
    if route in {'elsevier-api', 'wiley-api'}:
        name = 'elsevier-api-key' if route == 'elsevier-api' else 'wiley-tdm-token'
        (root / name).write_text('test-token')
        (root / name).chmod(0o600)
    if route == 'pmc-cloud':
        monkeypatch.setattr(mod, 'pmc_pdf', lambda *args: fixture_pdf(1))
    (root / 'retained.pdf').write_bytes(fixture_pdf(1 if route == 'connector' else 6))
    result = mod.acquire(current['doi'])
    assert ('connector-visit', None) in calls
    assert not any(path.endswith('acquire-attachment') for path, _ in calls)
    if route == 'connector':
        assert not result['ok'] and 'Incomplete' in result['stop_reason']
    else:
        assert result['ok'] and result['route'] == 'connector'
        assert route in result['skipped_routes'][0]


@pytest.mark.parametrize('route', ['auto', 'browser'])
@pytest.mark.parametrize('outcome', ['success', 'stale', 'failed'])
def test_refetch_previews_then_verifies_before_removing(runtime, monkeypatch, route, outcome):
    current, calls, root = runtime
    current.update(doi='10.1371/test')
    (root / 'retained.pdf').write_bytes(fixture_pdf(6))
    old_path = root / 'old.pdf'
    old_path.write_bytes(fixture_pdf(1))
    original_get = mod.ZoteroLocalAPI.get
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'items', lambda self, **kwargs: [
        {'key': 'PARENT', 'data': {'DOI': current['doi'], 'itemType': 'journalArticle'}}])
    def get(self, path):
        if path.endswith('children'):
            return [{'key': 'OLDPDF', 'data': {'contentType': 'application/pdf'}}] + original_get(self, path)
        return original_get(self, path)
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'get', get)
    original_text = mod.ZoteroLocalAPI.get_text
    monkeypatch.setattr(mod.ZoteroLocalAPI, 'get_text', lambda self, path:
        old_path.as_uri() if 'OLDPDF' in path else original_text(self, path))
    # The fake library starts with just the incomplete attachment.
    current['has_pdf'] = False
    original = mod.request
    def request(url, **kwargs):
        if 'crossref' in url:
            return b'{"message":{"page":"10-19"}}'
        if 'unpaywall' in url:
            return b'{"oa_locations":[{"url_for_pdf":"https://repository.example/paper.pdf"}]}'
        return original(url, **kwargs)
    monkeypatch.setattr(mod, 'request', request)
    removed = []
    original_plugin = mod.ZoteroPluginClient._request
    def plugin(self, path, **kwargs):
        payload = kwargs['payload']
        if payload.get('action') == 'replace':
            assert mod.pdf_bytes((root / 'retained.pdf').read_bytes())
            assert payload['old_key'] == 'OLDPDF' and payload['new_key'] == 'PDFKEY'
            removed.append(payload)
            return {}
        return original_plugin(self, path, **kwargs)
    monkeypatch.setattr(mod.ZoteroPluginClient, '_request', plugin)
    ordinary = mod.acquire(current['doi'])
    assert not ordinary['ok'] and '--refetch' in ordinary['stop_reason']
    preview = mod.acquire(current['doi'], refetch=True, route=route)
    assert preview['mode'] == 'dry-run' and preview['approval_required']
    assert not removed and not any(mode == 'apply' or path == 'connector-visit' for path, mode in calls)
    if outcome == 'stale':
        old_path.write_bytes(fixture_pdf(1) + b'\nchanged')
    if outcome == 'failed':
        (root / 'retained.pdf').write_bytes(fixture_pdf(1))
    result = mod.acquire(current['doi'], refetch=True, route=route, apply=True, preview_sha256=preview['preview_sha256'])
    assert bool(removed) == (outcome == 'success')
    assert result['ok'] == (outcome == 'success')
    if outcome == 'stale':
        assert 'preview changed' in result['stop_reason']
