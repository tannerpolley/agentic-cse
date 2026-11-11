"""Rebuildable, read-only index of project-owned scientific tables.

Values are strings: the catalog preserves printed precision, qualifiers and units.
Recognizers use declarations, never repository names or inferred physical units.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET
import zipfile

import duckdb

from .scientific_data import _sha256

SKIP = {'venv', 'env', 'node_modules', '__pycache__', '_site', 'tmp', 'temp', 'build',
        '_build', 'dist', 'downstream', 'pytest_tmp', '_freeze', 'latex-build', 'tex-build'}
TABULAR = {'.csv', '.tsv', '.parquet', '.xlsx', '.xls'}
HASH_LIMIT = 64 * 1024 * 1024
SCHEMA = {
 'datasets': 'dataset project path kind format row_count:BIGINT columns size:BIGINT modified:DOUBLE sha256 system components property source_key doi zotero_key locator temperature_range source_identity:BOOLEAN units:BOOLEAN uncertainty:BOOLEAN mapped:BOOLEAN layout reason duplicate_of digitization_evidence metadata',
 'points': 'dataset row:BIGINT project kind path system property value unit unit_source uncertainty uncertainty_unit conditions source_key locator doi',
 'parameters': 'dataset row:BIGINT project kind path system property component family value unit source_key locator doi',
 'sources': 'source_key project kind system property doi zotero_key title datasets:BIGINT points:BIGINT',
 'results': 'project kind system property source_key path count:BIGINT size:BIGINT modified:DOUBLE',
}


def text(value):
    if value is None:
        return ''
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)


def first(row, *keys):
    if not isinstance(row, dict):
        return ''
    return next((text(row[k]) for k in keys if row.get(k) not in (None, '', [], {})), '')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'), parse_float=str)


def walk(root):
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIP and not d.endswith('.egg-info')
                         and not (Path(base) / d).is_symlink()
                         and not (Path(base) / d / '.git').exists()
                         and not (d == 'builds' and Path(base).name == 'latex'))
        for name in sorted(files):
            path = Path(base) / name
            if not path.is_symlink():
                yield path


def table_rows(path, connection):
    suffix = path.suffix.lower()
    if suffix in {'.csv', '.tsv'}:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader((line for line in handle if not line.startswith('#')),
                                    delimiter='\t' if suffix == '.tsv' else ',')
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields) or not all(fields):
                raise ValueError('empty or duplicate column names')
            rows = list(reader)
            if any(None in row or None in row.values() for row in rows):
                raise ValueError('ragged table')
            return fields, rows
    if suffix == '.parquet':
        cursor = connection.execute('SELECT * FROM read_parquet(?)', [str(path)])
        fields = [col[0] for col in cursor.description]
        return fields, [dict(zip(fields, map(text, row))) for row in cursor.fetchall()]
    if suffix == '.xlsx':
        # Read all worksheets without Excel, extensions or new dependencies.
        with zipfile.ZipFile(path) as archive:
            ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(e.itertext()) for e in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
            fields, rows = [], []
            for name in sorted(n for n in archive.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+.xml', n)):
                sheet = []
                for row in ET.fromstring(archive.read(name)).findall('.//m:sheetData/m:row', ns):
                    values = {}
                    for cell in row:
                        col = re.match(r'[A-Z]+', cell.get('r', 'A1'))[0]
                        val = cell.find('m:v', ns)
                        value = val.text or '' if val is not None else ''.join(cell.findtext('m:is/m:t', '', ns))
                        values[col] = strings[int(value)] if cell.get('t') == 's' and value else value
                    sheet.append(values)
                if sheet:
                    header = sheet[0]
                    for value in header.values():
                        if value not in fields: fields.append(value)
                    rows.extend({header[k]: v for k, v in row.items() if k in header} for row in sheet[1:])
            return fields, rows
    raise ValueError('legacy Excel binary format unsupported; dataset only')


def safe_sidecar(path, root):
    """A sidecar must be a regular file reached without traversing any symlink."""
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        return False
    relative = path.relative_to(root)
    if any(root.joinpath(*relative.parts[:index]).is_symlink()
           for index in range(1, len(relative.parts) + 1)):
        return False
    return path.resolve().is_relative_to(root)


def result_directory(parts):
    if 'analyses' in parts and 'figures' in parts:
        index = parts.index('figures')
        if 'output' in parts[index + 1:]:
            return parts.index('output', index + 1)
    if 'results' in parts:
        return parts.index('results')
    if 'data' in parts and 'processed' in parts:
        return parts.index('processed')
    return None


def metadata_for(path, root):
    """Only scoped sidecars: a packet file declaration or package resource list."""
    metadata = {}
    for parent in (path.parent, *path.parent.parents):
        if parent != root and root not in parent.parents:
            break
        packet = parent / 'packet.toml'
        package = parent / 'dataset.json'
        if safe_sidecar(packet, root):
            data = tomllib.loads(packet.read_text())
            entry = next((f for f in data.get('files', []) if (parent / f.get('path', '')).resolve() == path), None)
            if entry:
                sources = [s for s in data.get('sources', []) if isinstance(s, dict) and s.get('source_id') in entry.get('source_refs', [])]
                metadata.update(entry)
                metadata['sources'] = sources
                if len(sources) == 1: metadata.update(sources[0])
                metadata['domains'] = data.get('domains', [])
            break
        if safe_sidecar(package, root):
            data = read_json(package)
            if any((parent / r.get('path', '')).resolve() == path for r in data.get('resources', [])):
                metadata.update(data)
                if isinstance(data.get('source'), dict): metadata.update(data['source'])
            break
    for candidate in (path.with_suffix('.metadata.json'), path.with_name(path.stem + '_metadata.json'), path.with_suffix('.json')):
        if candidate != path and safe_sidecar(candidate, root):
            data = read_json(candidate)
            if isinstance(data, dict): metadata.update(data)
    return metadata


def identity(row):
    return first(row, 'source_key', 'source_id', 'citation_key', 'zotero_key', 'external_source_id', 'citation', 'source', 'reference_source')


def locator(row):
    direct = first(row, 'source_locator', 'source_table_or_figure', 'locator')
    return direct or '; '.join(f'{key}={row[key]}' for key in ('table', 'source_table', 'page', 'printed_page', 'pdf_page_1based', 'source_pdf_page', 'source_row') if row.get(key))


def numeric(value):
    try:
        return bool(value) and Decimal(str(value)).is_finite()
    except InvalidOperation:
        return False


def coordinate_column(column):
    name = column.casefold()
    return 'pixel' in name or '_px' in name or name.endswith('_pt') or bool(re.fullmatch(r'pdf_.*_points?', name))


def digitization_evidence(path, fields):
    return [reason for reason, present in (
        ('name', 'digitiz' in path.name.casefold()),
        ('coordinates', any(coordinate_column(column) for column in fields))) if present]


def digitized_row(row, method_fields):
    affirmative = {'true', 'yes', '1', 'figure', 'manual', 'vector', 'reviewed_overlay', 'reviewed',
                   'verified', 'digitized', 'digitised', 'manual digitization', 'pdf vector', 'figure-derived'}
    return any(text(row.get(key)).strip().casefold() in affirmative
               for key in method_fields)


# Approximate selection only; excluded fields remain verbatim in conditions.
HELPER_WORDS = ('tolerance', 'accuracy', 'reproducibility', 'standard_deviation', 'sigma',
                'uncertainty', 'predicted', 'calculated', 'model', 'conversion', 'temperature')


def helper_column(column):
    return any(word in column.casefold().replace('-', '_').replace(' ', '_') for word in HELPER_WORDS)


def quantity_column(column):
    """Select candidate quantities only; never return or interpret a unit."""
    return not column.casefold().startswith('log10_k') and bool(re.search(r'_(?:mol|kg|g|Pa|kPa|MPa|K|C|J|kJ)(?:_|$)', column))


def map_rows(rows, fields, meta, kind):
    points, parameters = [], []
    layouts = set()
    if kind in {'result', 'manifest', 'plant'}:
        return points, parameters, '', f'{kind} inventory only'
    declared = meta.get('units', {})
    if not isinstance(declared, dict): declared = {}
    axes = meta.get('axes', {})
    if not isinstance(axes, dict): axes = {}
    method_fields = [key for key in fields if 'digitiz' in key.casefold() or key.casefold() in {'extraction', 'extraction_method', 'extraction_mode', 'extraction_type'}]
    for number, row in enumerate(rows, 1):
        row_kind = 'digitized' if kind == 'digitized' or digitized_row(row, method_fields) else 'measurement'
        combined = {**meta, **{k: v for k, v in row.items() if v not in ('', None)}}
        source, loc = identity(combined), locator(combined)
        component = first(row, 'component_id', 'component', 'component_or_pair')
        if not component and row.get('component_id_a') and row.get('component_id_b'):
            component = text([row['component_id_a'], row['component_id_b']])
        family = first(row, 'family')
        unit = first(row, 'value_unit', 'unit', 'units')
        if row_kind != 'digitized' and component and family and unit and numeric(row.get('value')):
            parameters.append(dict(row=number, component=component, family=family, value=text(row['value']), unit=unit,
                                   source_key=source, locator=loc, doi=first(combined, 'doi')))
            layouts.add('long parameters')
            continue
        if not source or not loc:
            continue
        values = []
        prop = first(row, 'property', 'quantity')
        if prop and unit and numeric(row.get('value')):
            values.append((prop, text(row['value']), unit, 'declared', first(row, 'uncertainty_value', 'uncertainty'), first(row, 'uncertainty_unit')))
            layouts.add('long values with units')
        else:
            for col in fields:
                if helper_column(col) or coordinate_column(col) or col.casefold().startswith(('t_', 'u_')):
                    continue
                if re.search(r'(?:^|_)(?:id|row|page|index|vertex|rounding|unit|units)(?:_|$)', col, re.I):
                    continue
                spec = axes.get(col, {})
                if not isinstance(spec, dict): spec = {}
                unit_declaration = declared.get(col, '')
                explicit_unit = first(row, col + '_unit') or (unit_declaration if isinstance(unit_declaration, str) else first(unit_declaration, 'unit')) or first(spec, 'unit') or (unit if col == 'value' else '')
                axis_property = first(row, col + '_property', col + '_quantity') or first(spec, 'property', 'quantity')
                if col in {'x', 'y'} and not (axis_property or explicit_unit):
                    continue
                if not (explicit_unit or quantity_column(col) or axis_property) or not numeric(row.get(col)):
                    continue
                # A name selects a column, but contributes no text to its unit.
                unit_source = 'declared' if explicit_unit else 'column name'
                property_name = axis_property if explicit_unit and axis_property else col
                values.append((property_name, text(row[col]), explicit_unit, unit_source,
                               first(row, col + '_uncertainty', 'u_' + col),
                               first(row, col + '_uncertainty_unit', 'u_' + col + '_unit')))
            if values: layouts.add('wide quantities')
        for prop, value, unit, unit_source, uncertainty, uncertainty_unit in values:
            points.append(dict(row=number, kind=row_kind, system=first(combined, 'system', 'chemical_system'), property=prop,
                               value=value, unit=unit, unit_source=unit_source,
                               uncertainty=uncertainty, uncertainty_unit=uncertainty_unit,
                               conditions=json.dumps(row, ensure_ascii=False), source_key=source, locator=loc,
                               doi=first(combined, 'doi')))
    reason = ''
    if not points and not parameters:
        contexts = [meta, *rows]
        if not any(identity(r) for r in contexts): reason = 'source identity not stated'
        elif not any(locator(r) for r in contexts): reason = 'source locator not stated'
        else: reason = 'no recognized numeric quantity columns'
    return points, parameters, ', '.join(sorted(layouts)), reason


def json_parameters(data):
    """Canonical Parameters: component/pair coefficients with explicit magnitude/unit."""
    rows = []
    if not isinstance(data, dict): return rows
    for group in ('components', 'pairs'):
        for entry in data.get(group, []):
            if not isinstance(entry, dict): continue
            component = first(entry, 'component_id', 'component_ids', 'pair')
            if not component and entry.get('component_id_a') and entry.get('component_id_b'):
                component = text([entry['component_id_a'], entry['component_id_b']])
            for coefficient in entry.get('coefficients', []):
                if not isinstance(coefficient, dict): continue
                value = coefficient.get('value', {})
                provenance = coefficient.get('provenance', {})
                if isinstance(value, dict) and value.get('unit') and numeric(value.get('magnitude')) and component and coefficient.get('family'):
                    rows.append(dict(component_id=component, family=coefficient['family'], value=text(value['magnitude']), unit=value['unit'], **provenance))
            for family, fixed in entry.get('fixed', {}).items():
                value = fixed.get('value', {}) if isinstance(fixed, dict) else {}
                if isinstance(value, dict) and value.get('unit') and numeric(value.get('magnitude')):
                    rows.append(dict(component_id=component, family=family, value=text(value['magnitude']), unit=value['unit'], **fixed.get('provenance', {})))
    return rows


def registry_roots(corpus):
    domain = corpus / 'data/domains/thermophysical'
    inventory = domain / 'normalized/registry-records.csv'
    if not inventory.exists(): return []
    roots = []
    with inventory.open(newline='') as handle:
        for row in csv.DictReader(handle):
            if row['record_type'] != 'dataset': continue
            path = (domain / 'source/registry' / row['source_path']).resolve()
            if not path.is_relative_to((domain / 'source/registry').resolve()):
                raise ValueError('registry inventory path escapes snapshot')
            if path.is_file(): roots.append(('registry-snapshot', path.parent))
    return roots


def build_catalog(roots, output, *, corpus=None):
    started = time.monotonic()
    roots = [(project, Path(root).expanduser().resolve()) for project, root in roots]
    if corpus is not None: roots += registry_roots(Path(corpus))
    output = Path(output).expanduser().resolve()
    if any(output == root or output.is_relative_to(root) for _, root in roots) or (corpus and output.is_relative_to(Path(corpus).resolve())):
        raise ValueError('catalog output must be outside research roots and corpus')
    for _, root in roots:
        if not root.is_dir(): raise ValueError(f'catalog root does not exist: {root}')
    output.mkdir(parents=True, exist_ok=True)
    tables = {name: [] for name in SCHEMA}
    warnings = []
    source_metadata = {}
    summaries = {}
    seen = set()
    with duckdb.connect(':memory:') as reader:
        reader.execute('SET threads = ?', [int(os.environ.get('AGENT_HEAVY_CORES', '1'))])
        for project, root in roots:
            print(f'Scanning {project}: {root}', flush=True)
            for path in walk(root):
                if path in seen: continue
                seen.add(path)
                parts = path.relative_to(root).parts
                result_index = result_directory(parts)
                is_result = result_index is not None
                figure_json = is_result and parts[result_index] == 'output' and path.suffix.lower() == '.json'
                stat = path.stat()
                if is_result and path.suffix.lower() not in TABULAR and not figure_json:
                    index = result_index
                    analysis = str(root.joinpath(*parts[:index + 1]))
                    summary = summaries.setdefault((project, analysis), dict(project=project, kind='result', path=analysis, count=0, size=0, modified=0))
                    summary['count'] += 1; summary['size'] += stat.st_size
                    summary['modified'] = max(summary['modified'], stat.st_mtime)
                    continue
                if path.suffix.lower() not in TABULAR | {'.json'}: continue
                dataset = hashlib.sha256(str(path).encode()).hexdigest()[:24]
                row = dict(dataset=dataset, project=project, path=str(path), format=path.suffix[1:], size=stat.st_size,
                           modified=stat.st_mtime, mapped=False, source_identity=False, units=False, uncertainty=False)
                kind = ('result' if is_result else 'manifest' if any('manifest' in p.lower() or 'inventory' in p.lower() for p in parts)
                        else 'parameters' if any('parameter' in p.casefold() for p in (path.name, path.parent.name))
                        else 'plant' if path.name.startswith('NCCC_') else 'measurement')
                row['kind'] = kind
                try:
                    row['sha256'] = _sha256(path) if not is_result or stat.st_size <= HASH_LIMIT else ''
                    meta = metadata_for(path, root)
                    unsupported_json = False
                    if path.suffix.lower() == '.json':
                        data = read_json(path)
                        values = json_parameters(data)
                        unsupported_json = not bool(values)
                        if is_result:
                            kind = 'result'
                        elif not values and (path.name == 'sources.json'
                                             or any(word in path.name.casefold() for word in ('manifest', 'inventory'))
                                             or isinstance(data, dict) and isinstance(data.get('sources'), list)):
                            declared = data.get('sources', []) if isinstance(data, dict) else data
                            values = [item for item in declared if isinstance(item, dict)] if isinstance(declared, list) else []
                            kind = 'manifest'
                        elif values:
                            kind = 'parameters'
                        else:
                            parameter_content = isinstance(data, dict) and any('parameter' in key.casefold() or key in {'coefficients', 'fitted_values', 'fit_result'} for key in data)
                            if 'parameter' in path.name.casefold() or parameter_content:
                                kind = 'parameters'
                            else:
                                continue
                        fields = list(dict.fromkeys(key for value in values for key in value))
                        meta = {**meta, **{k: v for k, v in data.items() if k != 'components'}} if isinstance(data, dict) else meta
                        row['kind'] = kind
                    else: fields, values = table_rows(path, reader)
                    evidence = [] if is_result else digitization_evidence(path, fields)
                    if evidence and not is_result:
                        kind = 'digitized'
                    row.update(row_count=len(values), columns=text(fields), metadata=text(meta), digitization_evidence=text(evidence))
                    if unsupported_json:
                        if kind not in {'parameters', 'manifest'}: continue
                        points, parameters, layout, reason = [], [], '', 'unsupported JSON layout'
                        row['row_count'] = None
                    else:
                        points, parameters, layout, reason = map_rows(values, fields, meta, kind)
                    if points: kind = 'digitized' if all(p['kind'] == 'digitized' for p in points) else 'measurement'
                    elif parameters and not points: kind = 'parameters'
                    row['kind'] = kind
                    if path.suffix.lower() == '.json' and parameters: layout = 'canonical parameter JSON'
                    row.update(mapped=bool(points or parameters), layout=layout, reason=reason)
                    contexts = [meta, *values]
                    for context in contexts:
                        key = identity(context)
                        if key:
                            source = source_metadata.setdefault(key, dict(source_key=key, doi='', zotero_key='', title=''))
                            for field, aliases in {'doi': ('doi',), 'zotero_key': ('zotero_key', 'zotero_parent_key'), 'title': ('title', 'citation')}.items():
                                if value := first(context, *aliases): source[field] = value
                    for field, aliases in {'system': ('system', 'chemical_system'), 'components': ('components', 'component_id'),
                                           'property': ('property', 'quantity'), 'doi': ('doi',),
                                           'zotero_key': ('zotero_key', 'zotero_parent_key')}.items():
                        row[field] = text(sorted({first(c, *aliases) for c in contexts if first(c, *aliases)}))
                    row['source_key'] = text(sorted({identity(c) for c in contexts if identity(c)}))
                    row['locator'] = text(sorted({locator(c) for c in contexts if locator(c)}))
                    row['temperature_range'] = text({key: [v[0], v[-1]] for key in fields if 'temperature' in key.lower() or key == 'T_K'
                                                     if (v := sorted([r[key] for r in values if numeric(r.get(key))], key=lambda x: Decimal(x)))})
                    row['source_identity'] = any(identity(c) for c in contexts)
                    row['units'] = bool(parameters) or any(p['unit_source'] == 'declared' for p in points) or any(any('unit' in k and bool(v) for k, v in c.items()) for c in contexts)
                    row['uncertainty'] = any(any('uncertainty' in k and bool(v) for k, v in c.items()) for c in contexts)
                    for target, mapped in [('points', points), ('parameters', parameters)]:
                        for value in mapped:
                            tables[target].append({**dict(dataset=dataset, project=project, kind='parameters' if target == 'parameters' else kind, path=str(path)), **value})
                except (OSError, ValueError, csv.Error, duckdb.Error, zipfile.BadZipFile, ET.ParseError) as exc:
                    row['reason'] = f'unreadable table: {exc}'
                    warnings.append(f'{path}: {exc}')
                tables['datasets'].append(row)
    tables['results'] = list(summaries.values())
    hashes = defaultdict(list)
    for row in tables['datasets']:
        if row.get('sha256'): hashes[row['sha256']].append(row)
    duplicates = [group for group in hashes.values() if len(group) > 1]
    for group in duplicates:
        for row in group: row['duplicate_of'] = text([r['dataset'] for r in group if r is not row])
    sources = source_metadata
    for row in tables['points'] + tables['parameters']:
        key = row['source_key']
        if key: sources.setdefault(key, dict(source_key=key, doi=row.get('doi', ''), zotero_key='', title=''))
    for row in tables['datasets']:
        if not row.get('metadata'): continue
        meta = json.loads(row['metadata'])
        declared = meta.get('sources', [])
        if not isinstance(declared, list): declared = []
        for source in [meta, *declared]:
            key = identity(source)
            if key:
                current = sources.setdefault(key, dict(source_key=key, doi='', zotero_key='', title=''))
                for field, aliases in {'doi': ('doi',), 'zotero_key': ('zotero_key', 'zotero_parent_key'), 'title': ('title', 'citation')}.items():
                    if value := first(source, *aliases): current[field] = value
        for key in json.loads(row.get('source_key') or '[]'):
            sources.setdefault(key, dict(source_key=key, doi='', zotero_key='', title=''))
    citations = defaultdict(set)
    point_counts = Counter(r['source_key'] for r in tables['points'])
    for row in tables['datasets']:
        for key in json.loads(row.get('source_key') or '[]'): citations[key].add(row['dataset'])
    for row in tables['points'] + tables['parameters']:
        citations[row['source_key']].add(row['dataset'])
    datasets_by_id = {row['dataset']: row for row in tables['datasets']}
    for key, source in sources.items():
        for field in ('project', 'kind', 'system', 'property'):
            source[field] = text(sorted({datasets_by_id[dataset].get(field, '') for dataset in citations[key]} - {''}))
        source['datasets'] = len(citations[key])
        source['points'] = point_counts[key]
    tables['sources'] = list(sources.values())
    with tempfile.TemporaryDirectory(dir=output, prefix='.catalog-') as staging:
        database = Path(staging) / 'catalog.duckdb'
        with duckdb.connect(str(database)) as connection:
            connection.execute('SET threads = ?', [int(os.environ.get('AGENT_HEAVY_CORES', '1'))])
            for name, spec in SCHEMA.items():
                fields = [part.split(':')[0] for part in spec.split()]
                constraints = ", CHECK(unit_source IS NOT NULL AND unit IS NOT NULL AND ((unit_source='column name' AND unit='') OR (unit_source='declared' AND unit<>'')))" if name == 'points' else ''
                connection.execute(f'CREATE TABLE {name} (' + ','.join('"' + part.replace(':', '" ') if ':' in part else f'"{part}" VARCHAR' for part in spec.split()) + constraints + ')')
                if tables[name]:
                    payload = Path(staging) / f'{name}.json'
                    payload.write_text(json.dumps([{k: r.get(k) for k in fields} for r in tables[name]], ensure_ascii=False))
                    connection.execute(f'INSERT INTO {name} BY NAME SELECT * FROM read_json(?, auto_detect=true, maximum_object_size=67108864)', [str(payload)])
        page = Path(staging) / 'catalog.html'
        page.write_text(render_page(tables, roots), encoding='utf-8')
        os.replace(database, output / database.name)
        os.replace(page, output / page.name)
    return dict(database=str(output / 'catalog.duckdb'), page=str(output / 'catalog.html'),
                counts={k: len(v) for k, v in tables.items()},
                project_kind=dict(Counter(f"{r['project']} / {r['kind']}" for r in tables['datasets'])),
                layouts=dict(Counter(r['layout'] for r in tables['datasets'] if r.get('layout'))),
                unmapped=sum(not r['mapped'] for r in tables['datasets']),
                reasons=Counter(r.get('reason', '') for r in tables['datasets'] if not r['mapped']).most_common(10),
                duplicate_groups=len(duplicates), duplicate_datasets=sum(map(len, duplicates)),
                hash_limit_bytes=HASH_LIMIT, seconds=round(time.monotonic() - started, 3), warnings=warnings)


def render_page(tables, roots=()):
    page_tables = {**tables, 'datasets': [{k: v for k, v in row.items() if k != 'metadata'}
                                         for row in tables['datasets']]}
    columns = {name: [part.split(':')[0] for part in spec.split()
                      if not (name == 'datasets' and part == 'metadata')]
               for name, spec in SCHEMA.items()}
    payload = json.dumps(page_tables, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    root_paths = json.dumps([(project, str(root)) for project, root in roots], ensure_ascii=False).replace('<', '\\u003c')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chemical engineering data catalog</title><style>
:root{color-scheme:light dark;font:14px/1.5 system-ui;--bg:#f5f7fa;--panel:#fff;--ink:#202c3d;--muted:#546478;--line:#dce2e9;--accent:#245bb3;--hover:#eef4fc}
@media(prefers-color-scheme:dark){:root{--bg:#131a24;--panel:#1c2633;--ink:#e1e8f2;--muted:#aab9cb;--line:#354356;--accent:#9cc3ff;--hover:#27384e}}
[hidden]{display:none!important}*{box-sizing:border-box}body{margin:0;padding:clamp(16px,3vw,40px);background:var(--bg);color:var(--ink)}h1{font-size:clamp(23px,3vw,32px);letter-spacing:-.03em;margin:0 0 8px}p{color:var(--muted);margin:8px 0 20px}button,input,select{font:inherit;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:6px 10px}button{cursor:pointer}button:hover{background:var(--hover)}:focus-visible{outline:3px solid var(--accent);outline-offset:2px}button:disabled{opacity:.45;cursor:default}nav{display:flex;gap:6px;flex-wrap:wrap;margin:24px 0 16px}nav button[aria-pressed=true]{background:var(--ink);color:var(--panel);border-color:var(--ink)}#toolbar,#filters,.paging{display:flex;align-items:center;gap:10px 16px;flex-wrap:wrap}#filters{display:contents}#toolbar{background:var(--panel);padding:16px;border:1px solid var(--line);border-radius:10px}label{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:13px;min-width:0}select{max-width:150px;text-overflow:ellipsis}input[type=search]{width:230px;max-width:100%;min-width:0}#result-control{margin:14px 0}#count{margin:0}.paging{justify-content:space-between;margin:18px 0 10px}.paging div{display:flex;gap:8px}#viewport{overflow:auto;max-height:58vh;border:1px solid var(--line);border-radius:8px;background:var(--panel)}table{border-collapse:collapse;width:100%;white-space:nowrap;text-align:left}th,td{border-bottom:1px solid var(--line);padding:10px 14px;max-width:180px;overflow:hidden;text-overflow:ellipsis}th{position:sticky;top:0;background:var(--panel);z-index:1;font-size:12px;color:var(--muted)}th button{border:0;padding:0;background:transparent;font-weight:600;white-space:nowrap}.number{text-align:right;font-variant-numeric:tabular-nums}tbody tr{cursor:pointer}tbody tr:hover,tbody tr[aria-selected=true]{background:var(--hover)}td.file{max-width:none;font-size:12px;font-family:ui-monospace,monospace}h2{font-size:18px;margin:24px 0 10px}#details{padding:18px;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow-wrap:anywhere}dl{margin:0;display:grid;grid-template-columns:150px minmax(0,1fr);gap:10px 20px}dt{color:var(--muted)}dd{margin:0;white-space:pre-wrap}#details table{table-layout:fixed;white-space:normal;font-size:13px}#details th{position:static;width:40%;overflow-wrap:anywhere}#details td{overflow-wrap:anywhere}a{color:var(--accent)}@media(max-width:600px){#toolbar{padding:12px}#filters{gap:10px}label{flex-wrap:wrap}select{max-width:100px}dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:10px}.paging{align-items:flex-start}th,td{padding:9px 12px}}
</style>
<h1>Chemical engineering data catalog</h1><p>Values, units and sources are exact copies of what files state; kind labels and column selection are automatic and approximate. Each row’s file path is the authority.</p>
<nav aria-label="Tables" id="tabs"></nav><div id="toolbar"><label>Search <input id="search" type="search" placeholder="Search all fields"></label><div id="filters"></div><button id="clear">Clear filters</button></div>
<label id="result-control"><input id="include-results" type="checkbox"><span id="result-label"></span></label>
<div class="paging"><p id="count" aria-live="polite"></p><div><button id="prev">Previous 100</button><button id="next">Next 100</button></div></div><div id="viewport" tabindex="0" aria-label="Catalog rows; scroll for more columns"><table><thead id="head"></thead><tbody id="body"></tbody></table></div><h2>Row details</h2><div id="details" tabindex="-1">Select a row to see all fields and its full file path.</div>
<script id="data" type="application/json">''' + payload + '</script><script id="schema" type="application/json">' + json.dumps(columns) + '</script><script id="roots" type="application/json">' + root_paths + '''</script><script>
const get=id=>document.getElementById(id),data=JSON.parse(get('data').textContent),columns=JSON.parse(get('schema').textContent),roots=JSON.parse(get('roots').textContent);
const collator=new Intl.Collator(undefined,{numeric:true}),valueCache=new Map();
const titles={dataset:'Internal identifier',project:'Project',kind:'Kind',system:'System',property:'Property',source_key:'Source',row_count:'Rows',path:'File',value:'Value',unit:'Unit',unit_source:'Unit from',component:'Component',family:'Family',locator:'Locator',doi:'DOI',zotero_key:'Zotero key',title:'Title',datasets:'Datasets',points:'Points',count:'Files',size:'Bytes',modified:'Modified',columns:'Columns',duplicate_of:'Duplicate of'};
const visible={datasets:['project','kind','system','property','source_key','row_count','path'],points:['system','property','value','unit','source_key','locator','project'],parameters:['component','family','value','unit','source_key','project'],sources:['source_key','title','doi','project','datasets','points'],results:['project','kind','system','property','source_key','path','count','size']};
const numeric=new Set(['value','row_count','row','size','count','datasets','points','modified']);
let tab='datasets',sort='',direction=1,offset=0,rows=[],filtered=[],timer;const filters={},tabs={};
function element(tag,text){const e=document.createElement(tag);e.textContent=text??'';return e}
function title(key){return titles[key]||key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase())}
function values(r,key){const raw=r[key];if(raw==null)return [];const v=String(raw);if(!v.startsWith('['))return [v];
if(!valueCache.has(v)){let parsed;try{parsed=JSON.parse(v)}catch{parsed=v}valueCache.set(v,(Array.isArray(parsed)?parsed:[parsed]).map(String))}return valueCache.get(v)}
function relativePath(r){const path=r.path||'';const root=roots.find(([project,root])=>project===r.project&&path.startsWith(root+'/'));return root?path.slice(root[1].length+1):path}
function display(r,key){if(key==='path'){const path=relativePath(r);return path.length>42?path.slice(0,10)+'…'+path.slice(-31):path}if(key==='unit'&&r.unit_source==='column name')return 'in column name';return values(r,key).join(', ')}
function choose(name){tab=name;rows=data[tab];sort='';direction=1;offset=0;get('filters').replaceChildren();for(const key of Object.keys(filters))delete filters[key];
for(const key of ['project','kind','system','property','source_key','unit_source']){const options=[...new Set(rows.flatMap(r=>values(r,key)).filter(Boolean))].sort();if(!options.length)continue;
const label=element('label',title(key)+' '),s=element('select');s.setAttribute('aria-label',title(key));s.append(element('option','All'));s.firstChild.value='';
for(const value of options){const o=element('option',value);o.value=value;s.append(o)}
filters[key]=s;label.append(s);get('filters').append(label);s.onchange=()=>{offset=0;update()}}
for(const [name,b] of Object.entries(tabs))b.setAttribute('aria-pressed',String(name===tab));
get('result-control').hidden=tab!=='datasets';get('details').replaceChildren(element('span','Select a row to see all fields and its full file path.'));update()}
function update(){const q=get('search').value.toLowerCase(),active=Object.entries(filters).filter(([k,s])=>s.value),hideResults=tab==='datasets'&&!get('include-results').checked;
filtered=!q&&!active.length&&!hideResults?rows.slice():rows.filter(r=>(!hideResults||r.kind!=='result')&&active.every(([k,s])=>values(r,k).includes(s.value))&&(!q||JSON.stringify(r).toLowerCase().includes(q)));
if(sort==='value'){const keyed=filtered.map(row=>({row,value:Number(row.value)}));
if(keyed.every(x=>Number.isFinite(x.value)))keyed.sort((a,b)=>direction*(a.value-b.value));
else keyed.sort((a,b)=>direction*collator.compare(a.row.value,b.row.value));filtered=keyed.map(x=>x.row)}
else if(sort)filtered.sort((a,b)=>{const x=a[sort]??'',y=b[sort]??'';return direction*(typeof x==='number'&&typeof y==='number'?x-y:collator.compare(String(x),String(y)))});draw()}
function draw(){get('count').textContent=filtered.length.toLocaleString()+' matching rows · '+(filtered.length?offset+1:0)+'–'+Math.min(offset+100,filtered.length).toLocaleString();get('head').replaceChildren();get('body').replaceChildren();
const hidden=data.datasets.filter(r=>r.kind==='result').length;get('result-label').textContent=get('include-results').checked?'Include model results':'Include model results ('+hidden.toLocaleString()+' hidden)';
const cols=visible[tab],tr=element('tr','');for(const key of cols){const th=element('th',''),b=element('button',title(key)+(sort===key?(direction===1?' ↑':' ↓'):''));th.setAttribute('scope','col');if(sort===key)th.setAttribute('aria-sort',direction===1?'ascending':'descending');if(numeric.has(key))th.className='number';b.onclick=()=>{direction=sort===key?-direction:1;sort=key;offset=0;update()};th.append(b);tr.append(th)}get('head').append(tr);
for(const r of filtered.slice(offset,offset+100)){const tr=element('tr','');tr.tabIndex=0;tr.setAttribute('aria-label','Details: '+cols.map(k=>display(r,k)).join(', '));tr.onclick=()=>{for(const row of get('body').children)row.setAttribute('aria-selected',String(row===tr));details(r)};tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tr.onclick();get('details').focus()}};
for(const key of cols){const td=element('td',display(r,key));td.title=String(r[key]??'');if(numeric.has(key))td.className='number';if(key==='path')td.className='file';tr.append(td)}get('body').append(tr)}
get('prev').disabled=offset===0;get('next').disabled=offset+100>=filtered.length}
function details(r){const dl=element('dl','');for(const key of columns[tab]){const dd=element('dd','');dl.append(element('dt',title(key)),dd);
if(key==='conditions'){let original;try{original=JSON.parse(r[key])}catch{}if(original&&typeof original==='object'){const table=element('table','');for(const [field,value] of Object.entries(original)){const row=element('tr','');row.append(element('th',field),element('td',typeof value==='object'?JSON.stringify(value):value));table.append(row)}dd.append(table);continue}}
if(key==='doi'){for(const doi of values(r,key)){if(/^10\\.\\d{4,9}\\//.test(doi)){const a=element('a',doi);a.href='https://doi.org/'+encodeURI(doi);a.rel='noreferrer';dd.append(a,element('span',' '))}else dd.append(element('span',doi))}}else dd.textContent=key==='unit'&&r.unit_source==='column name'?'in column name':values(r,key).join(', ')}get('details').replaceChildren(dl)}
for(const name of Object.keys(data)){const b=element('button',title(name)+' ('+data[name].length.toLocaleString()+')');b.onclick=()=>choose(name);tabs[name]=b;get('tabs').append(b)}
get('search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;update()},180)};
get('include-results').onchange=()=>{offset=0;update()};
get('clear').onclick=()=>{clearTimeout(timer);get('search').value='';get('include-results').checked=false;for(const s of Object.values(filters))s.value='';offset=0;update()};
get('prev').onclick=()=>{offset=Math.max(0,offset-100);draw()};get('next').onclick=()=>{offset+=100;draw()};choose(tab);
</script></html>'''
