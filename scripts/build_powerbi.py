"""Generate an inspectable native PBIP/PBIR project from the validated export contract.

Opening and refreshing in Power BI Desktop is a separate, explicitly recorded acceptance step.
"""
import argparse
import csv
import json
import uuid
from pathlib import Path


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def field(table, prop, measure=False):
    return {"Measure" if measure else "Column": {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def projection(table, prop, measure=False):
    return {"field": field(table, prop, measure), "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def build(root):
    root = Path(root).resolve()
    out = root / 'powerbi'
    model_dir = out / 'MedSupply.SemanticModel'
    report = out / 'MedSupply.Report'
    definition = report / 'definition'
    base = 'https://developer.microsoft.com/json-schemas/fabric/item/'
    write(out / 'MedSupply.pbip', {
        '$schema': 'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json',
        'version': '1.0', 'artifacts': [{'report': {'path': 'MedSupply.Report'}}],
        'settings': {'enableAutoRecovery': True}})
    write(model_dir / 'definition.pbism', {
        '$schema': base+'semanticModel/definitionProperties/1.0.0/schema.json', 'version': '4.2',
        'settings': {'qnaEnabled': False}})
    write(report / 'definition.pbir', {
        '$schema': base+'report/definitionProperties/2.0.0/schema.json', 'version': '4.0',
        'datasetReference': {'byPath': {'path': '../MedSupply.SemanticModel'}}})

    measures = {
        'Package Observations': "VAR Stamp = MAX(Snapshot[observed_at]) RETURN CALCULATE(COUNTROWS(FactObservation), Snapshot[observed_at] = Stamp)",
        'Source Reports': "VAR Stamp = MAX(Snapshot[observed_at]) RETURN CALCULATE(DISTINCTCOUNT(FactObservation[report_id]), Snapshot[observed_at] = Stamp)",
        'Critical Observations': "CALCULATE([Package Observations], FactObservation[critical_flag] = 1)",
        'Hospital Relevant': 'CALCULATE([Package Observations], FactObservation[hospital_relevant] = "ja")',
        'Source Rows': 'SUM(QualityAudit[source_rows])',
        'Accepted Rows': 'SUM(QualityAudit[accepted_rows])',
        'Rejected Rows': 'SUM(QualityAudit[rejected_rows])',
        'Acceptance Rate': 'DIVIDE([Accepted Rows], [Source Rows])',
        'Snapshot Count': 'COUNTROWS(ALL(Snapshot))',
        'Change Rows': 'VAR Stamp = MAX(Snapshot[observed_at]) RETURN IF([Snapshot Count] < 2, BLANK(), CALCULATE(COUNTROWS(FactChange), Snapshot[observed_at] = Stamp))',
        'Baseline Note': 'IF([Snapshot Count] < 2, "Baseline only: change history needs another observation.", "Changes compare observations; feed absence does not establish resolution.")',
    }
    types = {'critical_flag': 'int64', 'source_rows': 'int64', 'accepted_rows': 'int64', 'rejected_rows': 'int64'}
    date_cols = {'start_date', 'expected_end_date', 'source_updated', 'first_reported'}
    tables = []
    for name in ['FactObservation', 'FactChange', 'Snapshot', 'QualityAudit']:
        path = root / f'data/exports/{name}.csv'
        with path.open(encoding='utf-8', newline='') as f:
            headers = next(csv.reader(f))
        m_types = []
        columns = []
        for c in headers:
            dtype = types.get(c, 'dateTime' if c in date_cols else 'string')
            columns.append({'name': c, 'dataType': dtype, 'sourceColumn': c,
                            'summarizeBy': 'none', 'lineageTag': str(uuid.uuid5(uuid.NAMESPACE_URL, name+'.'+c))})
            m_types.append('{"'+c+'", '+('Int64.Type' if dtype=='int64' else 'type text')+'}')
        lines = ["let", f'    Source = Csv.Document(File.Contents(SourceFolder & "/{name}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
                 '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
                 '    Typed = Table.TransformColumnTypes(Headers, {'+', '.join(m_types)+'}, "en-GB")']
        if name == 'FactObservation':
            lines[-1] += ','
            transforms = ['{"'+c+'", each if _ = "" then null else DateTime.From(Date.FromText(_, [Format="yyyy-MM-dd", Culture="en-US"])), type nullable datetime}' for c in headers if c in date_cols]
            lines.append('    Dates = Table.TransformColumns(Typed, {'+', '.join(transforms)+'})')
        lines.extend(['in', '    Dates' if name=='FactObservation' else '    Typed'])
        table = {'name': name, 'columns': columns, 'lineageTag': str(uuid.uuid5(uuid.NAMESPACE_URL, name)),
                 'partitions': [{'name': name, 'mode': 'import', 'source': {'type': 'm', 'expression': lines}}]}
        if name == 'FactObservation':
            table['measures'] = [{'name': k, 'expression': v, 'formatString': '0.0%' if k=='Acceptance Rate' else '#,0',
                                  'displayFolder': 'Monitoring' if k not in {'Source Rows','Accepted Rows','Rejected Rows','Acceptance Rate'} else 'Quality'} for k,v in measures.items()]
            next(m for m in table['measures'] if m['name']=='Baseline Note').pop('formatString')
        tables.append(table)
        (out / 'power-query').mkdir(exist_ok=True, parents=True)
        (out / f'power-query/{name}.pq').write_text('\n'.join(lines), encoding='utf-8')

    dim_expression = ['let', '    LatestFirst = Table.Sort(FactObservation, {{"observed_at", Order.Descending}}),',
                      '    Source = Table.SelectColumns(Table.Buffer(LatestFirst), {"product_key", "pzn", "enr", "product", "ingredient", "manufacturer", "atc"}),',
                      '    DistinctProducts = Table.Distinct(Source, {"product_key"})', 'in', '    DistinctProducts']
    tables.append({'name':'DimProduct','columns':[{'name':c,'dataType':'string','sourceColumn':c,'summarizeBy':'none'} for c in ['product_key','pzn','enr','product','ingredient','manufacturer','atc']],
                   'partitions':[{'name':'DimProduct','mode':'import','source':{'type':'m','expression':dim_expression}}]})
    relationships = []
    for fact, dim, key in [('FactObservation','Snapshot','snapshot_id'), ('FactChange','Snapshot','snapshot_id'),
                            ('FactObservation','DimProduct','product_key'), ('FactChange','DimProduct','product_key')]:
        relationships.append({'name':str(uuid.uuid5(uuid.NAMESPACE_URL, fact+dim)), 'fromTable':fact,'fromColumn':key,
                              'toTable':dim,'toColumn':key,'crossFilteringBehavior':'oneDirection'})
    model = {'compatibilityLevel':1606, 'model':{'culture':'en-GB','defaultPowerBIDataSourceVersion':'powerBI_V3',
              'dataAccessOptions':{'legacyRedirects':True,'returnErrorValuesAsNull':True},
              'annotations':[{'name':'__PBI_TimeIntelligenceEnabled','value':'0'}],
              'expressions':[{'name':'SourceFolder','kind':'m','expression':'"'+(root/'data/exports').as_posix().replace('"','""')+'" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
              'tables':tables,'relationships':relationships}}
    write(model_dir/'model.bim', model)
    (out/'measures.dax').write_text('\n\n'.join(k+' = '+v for k,v in measures.items()),encoding='utf-8')

    write(definition/'version.json', {'$schema':base+'report/definition/versionMetadata/1.0.0/schema.json','version':'4.0.0'})
    write(definition/'report.json', {'$schema':base+'report/definition/report/3.3.0/schema.json',
        'themeCollection':{}, 'settings':{'useEnhancedTooltips':True,'defaultFilterActionIsDataFilter':True}})
    write(definition/'pages/pages.json', {'$schema':base+'report/definition/pagesMetadata/1.0.0/schema.json',
        'pageOrder':['Monitor','Quality'],'activePageName':'Monitor'})

    def visual(page, name, kind, x,y,w,h,query=None,text=None,title=None):
        obj = {'$schema':base+'report/definition/visualContainer/2.13.0/schema.json','name':name,
               'position':{'x':x,'y':y,'width':w,'height':h,'z':y+x,'tabOrder':y+x},
               'visual':{'visualType':kind,'drillFilterOtherVisuals':True}}
        v=obj['visual']
        if query:
            v['query']={'queryState':query}
        if text:
            v['objects']={'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':text,'textStyle':{
                'fontFamily':'Segoe UI','fontSize':'23pt' if name=='Title' else '11pt','color':'#193B39'}}]}]}}]}
        if title:
            v['visualContainerObjects']={'title':[{'properties':{'show':literal('true'),'text':literal("'"+title+"'")}}]}
        write(definition/f'pages/{page}/visuals/{name}/visual.json', obj)

    for page in ['Monitor','Quality']:
        write(definition/f'pages/{page}/page.json', {'$schema':base+'report/definition/page/2.0.0/schema.json',
            'name':page,'displayName':'01 · Shortage monitor' if page=='Monitor' else '02 · Data quality',
            'displayOption':'FitToPage','width':1280,'height':800})
        visual(page,'Title','textbox',28,18,1200,60,text='MEDSUPPLY / '+('REPORTED SHORTAGES' if page=='Monitor' else 'PIPELINE QUALITY'))
        note = ('Reported observations, not hospital stock. Expected end dates are estimates. Select a snapshot to inspect its records.' if page=='Monitor' else
                'Audit totals are independent of product filters. Each run reconciles source rows = valid candidates + rejected rows.')
        visual(page,'Subtitle','textbox',28,75,1200,50,text=note)

    for i,measure in enumerate(['Package Observations','Source Reports','Critical Observations','Hospital Relevant']):
        visual('Monitor','KPI'+str(i),'card',28+i*310,138,290,105,{'Values':{'projections':[projection('FactObservation',measure,True)]}},title=measure)
    visual('Monitor','SnapshotFilter','slicer',28,265,1200,70,{'Values':{'projections':[projection('Snapshot','observed_at')]}},title='Observation timestamp (UTC)')
    visual('Monitor','Reasons','clusteredBarChart',28,355,595,300,{
        'Category':{'projections':[projection('FactObservation','reason_type')]},
        'Y':{'projections':[projection('FactObservation','Package Observations',True)]}},title='Reported reason categories · packages')
    visual('Monitor','Manufacturers','clusteredBarChart',650,355,595,300,{
        'Category':{'projections':[projection('DimProduct','manufacturer')]},
        'Y':{'projections':[projection('FactObservation','Package Observations',True)]}},title='Reported manufacturer / authorisation holder')
    visual('Monitor','Baseline','card',28,675,1200,65,{'Values':{'projections':[projection('FactObservation','Baseline Note',True)]}})
    for i,measure in enumerate(['Source Rows','Accepted Rows','Rejected Rows','Acceptance Rate']):
        visual('Quality','KPI'+str(i),'card',28+i*310,138,290,105,{'Values':{'projections':[projection('FactObservation',measure,True)]}},title=measure)
    visual('Quality','Runs','tableEx',28,275,1200,300,{'Values':{'projections':[projection('QualityAudit',p) for p in ['observed_at','status','source_rows','accepted_rows','rejected_rows','error']]}},title='Ingestion run audit')
    visual('Quality','Definitions','textbox',28,605,1200,140,text='Quality gate: >5% rejected rows prevents publication. Conflicting product identities are quarantined together. First observation is a baseline. A missing record is not evidence of resolution. Search application: published text with report IDs and source dates.')
    print(json.dumps({'project':str(out/'MedSupply.pbip'),'tables':len(tables),'pages':2,'measures':len(measures)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='.')
    build(parser.parse_args().root)
