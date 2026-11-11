import json
import subprocess
from pathlib import Path

import duckdb
import pytest

from zotero_companion.catalog import build_catalog
from zotero_companion.scientific_data import query_table, ScientificDataError


@pytest.fixture
def catalog(tmp_path):
    root = tmp_path / 'research'
    root.mkdir()
    fixtures = {
        'long.csv': 'source_key,property,value,value_unit,uncertainty_value,uncertainty_unit,source_locator\npaper,density,1.00530,g/cm^3,0.0005,g/cm^3,Table 1\n',
        'packet/observation.csv': 'reading,reading_unit\n12.340,kPa\n',
        'wide.csv': 'source_key,source_locator,density_kg_m3,temperature_K\npaper2,Table 2,1033.30,298.15\n',
        'parameters.csv': 'component_id,family,value,unit,source_id,locator\nwater,mass,0.018,kg/mol,paper,Table 3\n',
        'digitized.csv': 'series,x,y,pixel_x,pixel_y\na,0.10,3.40,10,20\n',
        'sources.json': '[{"source_id":"paper","doi":"10.1234/example","title":"Fixture paper"}]',
        'unknown.csv': 'temperature,mystery\n300,42\n',
        'results/model.csv': 'x,y\n1,2\n',
        'results/model.txt': 'model log',
        '.worktrees/hidden.csv': 'x,y\n1,2\n',
    }
    for name, value in fixtures.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    (root / 'packet/packet.toml').write_text('[[sources]]\nsource_id = "packet-paper"\n[[files]]\npath = "observation.csv"\nsource_refs = ["packet-paper"]\nlocator = "Table 5"\n')
    (root / 'digitized.metadata.json').write_text(json.dumps({'sources': ['a descriptive citation'], 'source_key': 'figure', 'locator': 'Fig 1', 'axes': {'y': {'property': 'density', 'unit': 'kg/m3'}}}))
    (root / 'bundle.json').write_text(json.dumps({'components': [{'component_id': 'water', 'coefficients': [{'family': 'm', 'value': {'magnitude': '1.000', 'unit': 'dimensionless'}, 'provenance': {'source_id': 'paper', 'locator': 'Table 4'}}]}], 'pairs': [{'component_id_a': 'water', 'component_id_b': 'salt', 'coefficients': [{'family': 'kij', 'value': {'magnitude': '0.010', 'unit': 'dimensionless'}}]}]}))
    before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    report = build_catalog([('fixture', root)], tmp_path / 'output')
    assert before == {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    return report


def test_catalog_end_to_end(catalog):
    assert catalog['counts'] == {'datasets': 9, 'points': 4, 'parameters': 3, 'sources': 4, 'results': 1}
    assert query_table(Path(catalog['database']), "SELECT doi,title FROM sources WHERE source_key='paper'")['rows'] == [{'doi': '10.1234/example', 'title': 'Fixture paper'}]
    assert len(catalog['layouts']) == 4
    assert query_table(Path(catalog['database']), "SELECT value,unit,source_key FROM points WHERE source_key='packet-paper'")['rows'] == [{'value': '12.340', 'unit': 'kPa', 'source_key': 'packet-paper'}]
    db = Path(catalog['database'])
    points = query_table(db, 'SELECT property,value,unit FROM points ORDER BY value')['rows']
    assert {'property': 'density', 'value': '1.00530', 'unit': 'g/cm^3'} in points
    assert query_table(db, "SELECT kind,unit_source FROM points WHERE source_key='figure'")['rows'] == [{'kind': 'digitized', 'unit_source': 'declared'}]
    assert query_table(db, "SELECT mapped,reason FROM datasets WHERE path LIKE '%unknown.csv'")['rows'][0]['mapped'] is False
    assert query_table(db, "SELECT value, unit FROM parameters WHERE family='m'")['rows'][0] == {'value': '1.000', 'unit': 'dimensionless'}
    with pytest.raises(ScientificDataError):
        query_table(db, "SELECT * FROM read_csv('/etc/passwd')")
    with pytest.raises(ScientificDataError):
        query_table(db, 'DELETE FROM datasets')


def test_page_self_contained(catalog):
    page = Path(catalog['page']).read_text()
    assert '<script src=' not in page and '<link' not in page
    assert 'fetch(' not in page and 'XMLHttpRequest' not in page
    assert '1.00530' in page and 'g/cm^3' in page and 'unknown.csv' in page
    assert 'slice(offset,offset+100)' in page
    subprocess.run(['node', str(Path(__file__).with_name('catalog_page.mjs')), catalog['page']], check=True)
    with duckdb.connect(catalog['database'], read_only=True) as db:
        assert db.execute("SELECT metadata FROM datasets WHERE path LIKE '%digitized.csv'").fetchone()[0]


def test_units_are_declared_or_left_in_verbatim_column_name(tmp_path):
    root = tmp_path / 'research'
    root.mkdir()
    (root / 'values.csv').write_text(
        'source_key,source_locator,equilibrium_pco2_1e5_Pa,density,density_unit,u_equilibrium_pco2_1e5_Pa,absolute_print_tolerance_kg_m3,predicted_density_kg_m3,log10_K,reference_temperature_K\n'
        'paper,Table 1,0.12340,1.00530,g/cm^3,0.0002,0.01,999,-6.345,298.15\n')
    report = build_catalog([('fixture', root)], tmp_path / 'output')
    rows = query_table(Path(report['database']), 'SELECT property,value,unit,unit_source,uncertainty FROM points ORDER BY property')['rows']
    assert rows == [
        {'property': 'density', 'value': '1.00530', 'unit': 'g/cm^3', 'unit_source': 'declared', 'uncertainty': ''},
        {'property': 'equilibrium_pco2_1e5_Pa', 'value': '0.12340', 'unit': '', 'unit_source': 'column name', 'uncertainty': '0.0002'}]
    conditions = json.loads(query_table(Path(report['database']), 'SELECT conditions FROM points LIMIT 1')['rows'][0]['conditions'])
    assert conditions['absolute_print_tolerance_kg_m3'] == '0.01'
    assert conditions['predicted_density_kg_m3'] == '999'


def test_digitization_precedes_parameter_names_and_excludes_pdf_coordinates(tmp_path):
    root = tmp_path / 'research'
    folder = root / 'analyses/parameter-estimation/inputs/library'
    folder.mkdir(parents=True)
    (folder / 'observations_digitized.csv').write_text(
        'source_key,source_locator,loading_mol_kg,value,unit\npaper,Figure 1,0.1230,84.7772,mol_percent_total_amine\n')
    (folder / 'observations.csv').write_text(
        'source_key,source_locator,density_kg_m3,pdf_x_pt,pdf_y_pt,extraction\n'
        'paper,Figure 2,1033.30,10.5,20.5,PDF vector path from figure\n')
    (folder / 'declared.csv').write_text(
        'source_key,source_locator,pressure_Pa,extraction\npaper,Figure 3,101.300,figure\n')
    ordinary = folder / 'digitized_archive'
    ordinary.mkdir()
    (ordinary / 'tabulated.csv').write_text('source_key,source_locator,density_kg_m3,notes\npaper,Table 1,1000,curves were not digitized\n')
    (folder / 'mixed.csv').write_text('source_key,source_locator,pressure_Pa,extraction_method\npaper,Figure 4,10,figure\npaper,Table 2,20,tabulated\n')
    report = build_catalog([('fixture', root)], tmp_path / 'output')
    assert report['counts']['parameters'] == 0
    assert query_table(Path(report['database']), 'SELECT kind,property,value FROM points ORDER BY property,value')['rows'] == [
        {'kind': 'measurement', 'property': 'density_kg_m3', 'value': '1000'},
        {'kind': 'digitized', 'property': 'density_kg_m3', 'value': '1033.30'},
        {'kind': 'digitized', 'property': 'loading_mol_kg', 'value': '0.1230'},
        {'kind': 'digitized', 'property': 'pressure_Pa', 'value': '10'},
        {'kind': 'digitized', 'property': 'pressure_Pa', 'value': '101.300'},
        {'kind': 'measurement', 'property': 'pressure_Pa', 'value': '20'},
        {'kind': 'digitized', 'property': 'value', 'value': '84.7772'}]


@pytest.mark.parametrize('sidecar', ['values.metadata.json', 'values_metadata.json', 'values.json', 'packet.toml', 'dataset.json'])
def test_sidecars_never_follow_symlinks(tmp_path, sidecar):
    root = tmp_path / 'research'
    root.mkdir()
    (root / 'values.csv').write_text('property,value,unit\ndensity,1.2,kg/m3\n')
    outside = tmp_path / 'outside'
    if sidecar == 'packet.toml':
        outside.write_text('[[sources]]\nsource_id="outside"\n[[files]]\npath="values.csv"\nsource_refs=["outside"]\nlocator="Table 1"\n')
    else:
        outside.write_text(json.dumps({'source_key': 'outside', 'locator': 'Table 1', 'resources': [{'path': 'values.csv'}]}))
    (root / sidecar).symlink_to(outside)
    report = build_catalog([('fixture', root)], tmp_path / 'output')
    assert report['counts']['points'] == 0
    assert not query_table(Path(report['database']), "SELECT * FROM sources WHERE source_key='outside'")['rows']


def test_generated_trees_are_excluded_or_results(tmp_path, monkeypatch):
    import zotero_companion.catalog as module
    root = tmp_path / 'research'
    copied = root / 'docs/scientific/latex/builds/copy.csv'
    copied.parent.mkdir(parents=True)
    copied.write_text('source_key,source_locator,density_kg_m3\npaper,Table 1,999\n')
    output = root / 'analyses/study/figures/plot/output'
    output.mkdir(parents=True)
    (output / 'values.csv').write_text(copied.read_text())
    (output / 'parameters.json').write_text(json.dumps({'components': [{'component_id': 'water', 'coefficients': [{'family': 'm', 'value': {'magnitude': 1, 'unit': 'dimensionless'}}]}]}))
    (root / 'parameters_legacy.json').write_text(json.dumps({'coefficients': [1, 2, 3]}))
    (root / 't3.json').write_text(json.dumps({'status': 'complete'}))
    (output / 'receipt.json').write_text(json.dumps({'status': 'complete'}))
    hidden = root / 'preview/.openai'
    hidden.mkdir(parents=True)
    (hidden / 'hosting.json').write_text('{}')
    (hidden / 'values.csv').write_text(copied.read_text())
    scratch = root / '.tmp_local/pytest_tmp/values.csv'
    scratch.parent.mkdir(parents=True)
    scratch.write_text(copied.read_text())
    original = module._sha256
    def checked_hash(path):
        assert 'builds' not in path.parts and not any(part.startswith('.') for part in path.relative_to(root).parts[:-1])
        return original(path)
    monkeypatch.setattr(module, '_sha256', checked_hash)
    report = build_catalog([('fixture', root)], tmp_path / 'output')
    assert report['counts']['datasets'] == 3
    assert report['counts']['points'] == report['counts']['parameters'] == 0
    assert report['project_kind'] == {'fixture / result': 2, 'fixture / parameters': 1}
    assert query_table(Path(report['database']), "SELECT mapped,reason FROM datasets WHERE path LIKE '%parameters_legacy.json'")['rows'] == [{'mapped': False, 'reason': 'unsupported JSON layout'}]
