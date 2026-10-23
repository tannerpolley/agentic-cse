"""The everyday Connector must be present and claim each paper only once."""
import json

import pytest

from scripts.build_connector import build
from zotero_companion import acquire as acquisition
from zotero_companion import connector_job as bridge


def test_missing_extension_stops_before_pacing_or_publisher_visit(monkeypatch, tmp_path):
    clock = [0]
    monkeypatch.setattr(bridge, 'ensure_chrome', lambda: None)
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(bridge.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(bridge, 'connector_status', lambda: {'ready': False, 'error': bridge.SETUP})
    with acquisition.Safety(tmp_path / 'state.json') as safety:
        with pytest.raises(acquisition.AcquireStop, match='chrome://extensions'):
            bridge.connector_save('https://doi.org/10.1002/test', safety, 'wiley')
        assert 'wiley' not in safety.data


@pytest.mark.parametrize('url', [
    'http://public.example/a', 'file:///tmp/paper', 'https://localhost/a', 'https://127.1/a',
    'https://0x7f000001/a', 'https://10.0.0.1/a', 'https://172.16.1.1/a', 'https://192.168.1.1/a',
    'https://169.254.1.1/a', 'https://[::1]/a', 'https://[fc00::1]/a', 'https://[fe80::1]/a',
    'https://host.local/a', 'https://host.internal/a', 'https://singlelabel/a',
])
def test_non_public_job_stops_before_browser_or_submission(monkeypatch, tmp_path, url):
    def forbidden():
        pytest.fail('invalid destination reached Chrome startup')
    monkeypatch.setattr(bridge, 'ensure_chrome', forbidden)
    with acquisition.Safety(tmp_path / 'state.json') as safety:
        with pytest.raises(acquisition.AcquireStop):
            bridge.connector_save(url, safety, 'publisher')
        assert not safety.data


def test_job_roundtrip_counts_one_visit_and_preserves_session_and_refusal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bridge, 'ensure_chrome', lambda: None)
    monkeypatch.setattr(acquisition, 'require_vpn', lambda: None)
    monkeypatch.setattr(bridge.time, 'sleep', lambda seconds: None)
    class Plugin:
        job_id = None
        def _request(self, path, *, payload, **kwargs):
            calls.append(payload['action'])
            if payload['action'] == 'submit':
                self.job_id = payload['job']['id']
                assert payload['job']['doi'] == '10.1002/test'
                assert payload['job']['collection'] == 'COLL'
                assert payload['job']['existing_key'] == 'OLD'
                return {'id': self.job_id}
            if self.job_id:
                return {'job': {'id': self.job_id, 'publisher': 'wiley', 'state': 'done', 'result': {
                    'session_id': 'SESSION', 'url': 'https://WILEY.COM./paper', 'title': 'Just a moment', 'status': 403,
                    'stop': {'reason': 'Publisher access challenge: Cloudflare', 'host': 'wiley.com'}}}}
            return {'ready': True, 'version': '5.0.217'}
    plugin = Plugin()
    monkeypatch.setattr(bridge, 'ZoteroPluginClient', lambda *a, **k: plugin)
    with acquisition.Safety(tmp_path / 'state.json') as safety:
        result = bridge.connector_save('https://doi.org/10.1002/test', safety, 'wiley', collection='COLL', doi='10.1002/test', existing_key='OLD')
        assert result['session_id'] == 'SESSION' and result['status'] == 403
        assert safety.data['wiley']['count'] == 1
        assert safety.data['wiley.com']['last_browser'] > 0
        assert safety.data['wiley']['stop_reason'] == safety.data['wiley.com']['stop_reason']
    assert calls.count('submit') == 1


@pytest.mark.parametrize('permissions', [['tabs'], ['tabs', 'background']])
def test_connector_build_keeps_official_files_and_rejects_version_mismatch(tmp_path, permissions):
    source, output = tmp_path / 'official', tmp_path / 'agent'
    source.mkdir()
    (source / 'manifest.json').write_text(json.dumps({'version': '5.0.217', 'permissions': permissions, 'key': 'official-key'}))
    (source / 'background-worker.js').write_bytes(b'official worker\n')
    (source / 'native.js').write_bytes(b'official save logic\n')
    native = 'let options = { responseType: "arraybuffer", timeout: 60000, successCodes: false };'
    (source / 'itemSaver_background.js').write_text(native)
    build(source, output)
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest == {'version': '5.0.217', 'permissions': ['tabs', 'background'], 'name': 'Zotero Connector (agent)'}
    assert json.loads((source / 'manifest.json').read_text())['permissions'] == permissions
    assert json.loads((source / 'manifest.json').read_text())['key'] == 'official-key'
    assert (source / 'native.js').read_bytes() == (output / 'native.js').read_bytes()
    assert (output / 'background-worker.js').read_bytes() == b'official worker\n\nimportScripts("connector-agent.js");\n'
    assert (source / 'background-worker.js').read_bytes() == b'official worker\n'
    assert (source / 'itemSaver_background.js').read_text() == native
    assert (output / 'itemSaver_background.js').read_text() == native
    assert (output / 'cse-agent-job.html').is_file()
    record = json.loads((output / 'cse-agent-build.json').read_text())
    assert record['module_revision'] == int((output / 'connector-agent.js').read_text().split('MODULE_REVISION = ')[1].split(';')[0])
    (source / 'manifest.json').write_text('{"version":"5.0.218"}')
    with pytest.raises(ValueError, match='version mismatch'):
        build(source, output)


def test_attachment_check_hands_off_notifies_once_without_a_hold(monkeypatch, tmp_path):
    notices, calls = [], []
    monkeypatch.setattr(bridge, 'ensure_chrome', lambda: None)
    monkeypatch.setattr(acquisition, 'require_vpn', lambda: None)
    monkeypatch.setattr(bridge.shutil, 'which', lambda name: '/usr/bin/notify-send')
    monkeypatch.setattr(bridge.subprocess, 'run', lambda command, **kwargs: notices.append(command))
    monkeypatch.setattr(bridge.time, 'sleep', lambda seconds: pytest.fail('a handoff must not wait or retry'))
    class Plugin:
        job_id = None
        def _request(self, path, *, payload, **kwargs):
            calls.append(payload['action'])
            if payload['action'] == 'submit':
                self.job_id = payload['job']['id']
                return {}
            if not self.job_id:
                return {'ready': True}
            return {'job': {'id': self.job_id, 'state': 'done', 'result': {
                'handoff': 'https://pdf.example/check', 'url': 'https://publisher.example/paper',
                'stop': {'reason': 'Publisher check did not clear before the job deadline', 'host': 'pdf.example'}}}}
    monkeypatch.setattr(bridge, 'ZoteroPluginClient', Plugin)
    with acquisition.Safety(tmp_path / 'state.json') as safety:
        result = bridge.connector_save('https://publisher.example/paper', safety, 'elsevier')
        assert result['handoff'] == 'https://pdf.example/check'
        assert safety.data['elsevier']['stop_reason'] == safety.data['pdf.example']['stop_reason']
        assert 'cooldown_until' not in safety.data['elsevier']
    assert calls == ['status', 'submit', 'status']
    assert len(notices) == 1
    assert notices[0][2] == "elsevier needs you to save this paper; link in the agent's result"
