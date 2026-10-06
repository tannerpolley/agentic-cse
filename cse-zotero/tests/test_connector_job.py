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


def test_job_roundtrip_counts_one_visit_and_preserves_session_and_refusal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bridge, 'ensure_chrome', lambda: None)
    monkeypatch.setattr(acquisition, 'require_vpn', lambda: None)
    monkeypatch.setattr(bridge.time, 'sleep', lambda seconds: None)
    class Plugin:
        job_id = None
        running = False
        def _request(self, path, *, payload, **kwargs):
            calls.append(payload['action'])
            if payload['action'] == 'submit':
                self.job_id = payload['job']['id']
                assert payload['job']['doi'] == '10.1002/test'
                assert payload['job']['collection'] == 'COLL'
                return {'id': self.job_id}
            if self.job_id:
                return {'job': {'id': self.job_id, 'publisher': 'wiley', 'state': 'running' if self.running else 'done', 'result': {
                    'stopped_at': bridge.time.time() - 20,
                    'session_id': 'SESSION', 'url': 'https://WILEY.COM./paper', 'title': 'Just a moment', 'status': 403,
                    'stop': {'reason': 'Publisher access challenge: Cloudflare', 'host': 'wiley.com', 'cooldown': True}}}}
            return {'ready': True, 'version': '5.0.217'}
    plugin = Plugin()
    monkeypatch.setattr(bridge, 'ZoteroPluginClient', lambda *a, **k: plugin)
    with acquisition.Safety(tmp_path / 'state.json') as safety:
        result = bridge.connector_save('https://doi.org/10.1002/test', safety, 'wiley', collection='COLL', doi='10.1002/test')
        assert result['session_id'] == 'SESSION' and result['status'] == 403
        assert safety.data['wiley']['count'] == 1
        assert safety.data['wiley.com']['last_browser'] > 0
        bridge.reconcile_stop(safety, plugin)
        assert safety.data['wiley']['cooldown_until'] == safety.data['wiley.com']['cooldown_until']
        assert safety.data['wiley']['cooldown_until'] < bridge.time.time() + 86400
        plugin.running = True
        with pytest.raises(acquisition.AcquireStop, match='no parallel paper visits'):
            bridge.reconcile_stop(safety, plugin)
    assert calls.count('submit') == 1


def test_connector_build_keeps_official_files_and_rejects_version_mismatch(tmp_path):
    source, output = tmp_path / 'official', tmp_path / 'agent'
    source.mkdir()
    (source / 'manifest.json').write_text(json.dumps({'version': '5.0.217', 'permissions': ['tabs'], 'key': 'official-key'}))
    (source / 'background-worker.js').write_bytes(b'official worker\n')
    (source / 'native.js').write_bytes(b'official save logic\n')
    build(source, output)
    assert (source / 'manifest.json').read_bytes() == (output / 'manifest.json').read_bytes()
    assert (source / 'native.js').read_bytes() == (output / 'native.js').read_bytes()
    assert (output / 'background-worker.js').read_bytes() == b'official worker\n\nimportScripts("connector-agent.js");\n'
    assert (source / 'background-worker.js').read_bytes() == b'official worker\n'
    (source / 'manifest.json').write_text('{"version":"5.0.218"}')
    with pytest.raises(ValueError, match='version mismatch'):
        build(source, output)
