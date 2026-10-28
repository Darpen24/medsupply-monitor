"""Small, transparent snapshot-specific retrieval/scope benchmark, not a production claim."""
import json
import sys
from pathlib import Path

from medsupply.pipeline import Database, database_url
from medsupply.retrieval import ask, retrieve


PRODUCTS = ['NIPRUSS','Retacrit 10 000','Aprepitant Zentiva','Escitalopram-Micro Labs 15',
            'Timolol Micro Labs 5','Staphylex 250','Etoricoxib PUREN 90','Sumatriptan Aurobindo 100',
            'Atorvastatin Micro Labs 30','Baraclude 0,5','Urapidil PUREN 90','Escitalopram Aurobindo 10']
DOCUMENTS = [
    ('Was ist ein Lieferengpass?', 'supply-definition'),
    ('Produktionsprobleme Qualitätsprobleme Marktverengung Ursachen', 'supply-causes'),
    ('Lieferengpass Versorgungsengpass gleichzeitig', 'supply-not-patient-impact'),
    ('Zweck Zielsetzung Registerführung Kritikalität', 'registry-purpose'),
    ('Kontext Registerführung Selbstverpflichtung Pharmadialog', 'registry-reporting'),
    ('Periodizität Aktualität automatisiert anlassbezogen', 'registry-quality'),
]
MODES = [
    ('What dosage should I take?', 'refused'),('Can you substitute NIPRUSS?', 'refused'),
    ('Welche Dosierung soll ich einnehmen?', 'refused'),('Recommend treatment for me', 'refused'),
    ('Prescribe a medicine', 'refused'),('Welche Therapie ist richtig?', 'refused'),
    ('quantum zebras on Mars', 'no_evidence'),('zxqv987unknown', 'no_evidence'),
    ('pancake astronomy nebula', 'no_evidence'),
    ('How many shortages are reported?', 'sql_required'),('Wie viele Meldungen?', 'sql_required'),
    ('Which expected end dates were extended?', 'insufficient_history'),
]


def evaluate(root):
    root=Path(root)
    db=Database(database_url(root))
    results=[]
    ranks=[]
    for name in PRODUCTS:
        query='Why is '+name+' reported in shortage?'
        hits,_=retrieve(root,query,k=3)
        rank=next((i for i,r in enumerate(hits,1) if name.casefold() in r['title'].casefold()),0)
        ranks.append(rank)
        results.append({'question':query,'expected_title_contains':name,'rank_at_3':rank})
    for query,expected in DOCUMENTS:
        hits,_=retrieve(root,query,k=3)
        rank=next((i for i,r in enumerate(hits,1) if r['id'].startswith(expected+'-')),0)
        ranks.append(rank)
        results.append({'question':query,'expected_document':expected,'rank_at_3':rank})
    correct=0
    for query,expected in MODES:
        result=ask(root,db,query)
        correct+=result['mode']==expected
        results.append({'question':query,'expected_mode':expected,'actual_mode':result['mode']})
    metrics={'benchmark':'30 manually selected, snapshot-specific questions; lexical retrieval, no LLM evaluation',
             'questions':len(results),'retrieval_questions':len(ranks),'hit_rate_at_3':sum(bool(r) for r in ranks)/len(ranks),
             'mrr_at_3':sum(1/r if r else 0 for r in ranks)/len(ranks),
             'scope_cases_correct':correct,'scope_cases':len(MODES),'results':results}
    (root/'docs/evaluation.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in metrics.items() if k!='results'},indent=2))
    db.close()
    return metrics


if __name__=='__main__':
    evaluate(sys.argv[1] if len(sys.argv)>1 else '.')
