"""Fixed scripted drafting regression cases, deliberately not a model-quality score."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .drafts import DraftEngine,DraftRequest
from .generation import generate
from .generation_format import parse_proposal,PROMPT_VERSION
from .memory import Memory
from .messages import Message
from .store import Store


class ScriptedProvider:
    def __init__(self,response):self.response=response;self.calls=0
    def generate(self,packet):
        self.calls+=1
        return parse_proposal(self.response if isinstance(self.response,str) else json.dumps(self.response))


def evaluate_generation(manifest_path):
    path=Path(manifest_path);raw=path.read_bytes()
    if len(raw)>200_000:raise ValueError('Drafting manifest exceeds 200,000 bytes')
    manifest=json.loads(raw)
    if (not isinstance(manifest,dict) or type(manifest.get('version')) is not int or manifest['version']!=1
            or manifest.get('kind')!='synthetic generation contract regression' or manifest.get('messages')!='messages.jsonl'):
        raise ValueError('Invalid scripted drafting manifest')
    fixture=(path.parent/'messages.jsonl').read_bytes()
    if len(fixture)>200_000:raise ValueError('Synthetic messages exceed 200,000 bytes')
    messages=[Message.from_dict(json.loads(line)) for line in fixture.decode().splitlines() if line.strip()]
    cases=manifest.get('cases')
    if not isinstance(cases,list) or not 1<=len(cases)<=100:raise ValueError('Use 1-100 scripted drafting cases')
    rows=[];ids=set()
    for case in cases:
        if (not isinstance(case,dict) or not isinstance(case.get('id'),str) or not 1<=len(case['id'])<=80
                or case['id'] in ids or case.get('expected_status') not in ('needs_review','rejected','provider_abstained','needs_history')
                or case.get('semantic_label') not in ('supported','contradicted','not_applicable')
                or type(case.get('include_memory',False)) is not bool):raise ValueError('Invalid scripted drafting case')
        ids.add(case['id']);request=DraftRequest(**case['request']);provider=ScriptedProvider(case['response']);store=Store()
        try:
            store.ingest(messages);memory=Memory(store)
            if case.get('include_memory'):
                memory.create(owner=request.owner,contact=request.contact,kind='fact',text='Demo is planned for Thursday.',
                    sources=[('gmail','1')],reason='Synthetic fixture annotation',at='2026-09-02T00:00:00Z')
            engine=DraftEngine(store,memory);started=perf_counter()
            try:
                result=generate(engine,request,provider);status=result['status']
            except ValueError:
                result={};status='rejected'
            elapsed=perf_counter()-started
            requires_review=result.get('support_review_required',False)
            expected_calls=0 if case['expected_status']=='needs_history' else 1
            passed=(status==case['expected_status'] and provider.calls==expected_calls
                and (status!='needs_review' or requires_review is True))
            rows.append(dict(case_id=case['id'],expected_status=case['expected_status'],actual_status=status,
                provider_calls=provider.calls,support_review_required=requires_review,
                fixture_semantic_label=case['semantic_label'],passed=passed,elapsed_seconds=elapsed))
        finally:store.close()
    return dict(version=1,task=manifest['kind'],prompt_version=PROMPT_VERSION,
        benchmark_sha256=hashlib.sha256(raw+b'\0'+fixture).hexdigest(),case_count=len(rows),
        passed=sum(row['passed'] for row in rows),failed=sum(not row['passed'] for row in rows),cases=rows,
        contradicted_fixture_wordings_requiring_human_review=sum(row['fixture_semantic_label']=='contradicted'
            and row['actual_status']=='needs_review' for row in rows),
        model_inference_performed=False,limitation='Scripted response validation only, not factual accuracy, style preference or model quality. '
            'Fixture semantic labels are supplied by the author; the pipeline does not detect semantic contradictions. '
            'Elapsed time is infrastructure overhead, not model latency. No private messages or paid service.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    args=p.parse_args()
    try:result=evaluate_generation(args.manifest)
    except (ValueError,TypeError,KeyError,OSError) as exc:p.error(str(exc))
    print(json.dumps(result,indent=2));raise SystemExit(1 if result['failed'] else 0)


if __name__=='__main__':main()
