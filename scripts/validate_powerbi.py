"""Validate PBIR/PBIP JSON against Microsoft schemas and cross-check model bindings.

This is structural validation, not execution of M/DAX or Desktop rendering.
"""
import json
import sys
import urllib.request
from pathlib import Path

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7


def validate(root):
    root=Path(root)
    cache=root/'docs/schemas'
    cache.mkdir(exist_ok=True)
    schemas={}
    def load_schema(url):
        import hashlib
        if url not in schemas:
            local=cache/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')
            if local.exists():
                schema=json.loads(local.read_text())
            else:
                schema=json.load(urllib.request.urlopen(url,timeout=30))
                local.write_text(json.dumps(schema,indent=2))
            schema.setdefault('$id',url)
            schemas[url]=schema
        return schemas[url]
    registry=Registry(retrieve=lambda uri: Resource.from_contents(load_schema(uri),default_specification=DRAFT7))
    checked=0
    model=json.loads((root/'powerbi/MedSupply.SemanticModel/model.bim').read_text())['model']
    tables={t['name']:t for t in model['tables']}
    for rel in model['relationships']:
        for side in ['from','to']:
            assert rel[side+'Column'] in {c['name'] for c in tables[rel[side+'Table']]['columns']}
    def check_fields(value):
        if isinstance(value,dict):
            for kind in ['Column','Measure']:
                if kind in value and 'Expression' in value[kind]:
                    ref=value[kind]
                    entity=ref['Expression']['SourceRef'].get('Entity')
                    if entity:
                        key='columns' if kind=='Column' else 'measures'
                        assert ref['Property'] in {p['name'] for p in tables[entity].get(key,[])}, ref
            for child in value.values():
                check_fields(child)
        elif isinstance(value,list):
            for child in value:
                check_fields(child)
    for path in sorted((root/'powerbi').rglob('*')):
        if path.suffix not in {'.json','.pbip','.pbir','.pbism'}:
            continue
        data=json.loads(path.read_text())
        url=data.get('$schema')
        if not url:
            continue
        schema=load_schema(url)
        jsonschema.validators.validator_for(schema)(schema,registry=registry).validate(data)
        check_fields(data)
        checked+=1
    result={'schema_validated_files':checked,'native_tables':len(tables),'relationships':len(model['relationships']),
            'desktop_refresh':'not run','dax_execution':'not run','report_rendering':'not run'}
    (root/'docs/powerbi-validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    validate(sys.argv[1] if len(sys.argv)>1 else '.')
