#!/usr/bin/env python3
"""Verify the fail-closed PriceSmart full attempt and revised budget offline."""

from __future__ import annotations

import hashlib, json, tarfile
from pathlib import Path

REPORT=Path(__file__).resolve().parent
ROOT=REPORT.parents[2]
ARCHIVE=REPORT/'raw-attempt.tar.gz'
PROBE=ROOT/'reports/pricesmart/2026-09-02-discovery-probe/raw-capture.tar.gz'
PROBE_EVIDENCE=ROOT/'reports/pricesmart/2026-09-02-discovery-probe/evidence.json'
PROBE_SHA='b76f3910b19cc29d1c69baa1d70ac90298e8e95a7ba9d2e9be30643b3af5d848'

def sha(v): return hashlib.sha256(v).hexdigest()

def files(path):
 data=path.read_bytes()
 with tarfile.open(path,'r:gz') as t:
  members={m.name:m for m in t.getmembers() if m.isfile()}
  if any(n.startswith('/') or '..' in Path(n).parts for n in members):raise ValueError('unsafe_archive')
  out={n:t.extractfile(m).read() for n,m in members.items()}
 manifest=json.loads(out['manifest.json'])
 for row in manifest['files']:
  if len(out[row['path']])!=row['bytes'] or sha(out[row['path']])!=row['sha256']:raise ValueError('member_mismatch')
 return data,manifest,out

def reproduce():
 archive,manifest,payload=files(ARCHIVE)
 if sha(PROBE.read_bytes())!=PROBE_SHA:raise ValueError('probe_hash_mismatch')
 _,_,probe=files(PROBE)
 ledger=json.loads(payload['live/ledger.json'])
 req_name=next(n for n in payload if n.startswith('live/raw/requests/'))
 resp_name=next(n for n in payload if n.startswith('live/raw/responses/'))
 request=json.loads(payload[req_name]);response=json.loads(payload[resp_name]);decoded=json.loads(response['body_raw'])
 if ledger['post_attempts']!=1 or ledger['retries']!=0 or ledger['successful_pages']!=0:raise ValueError('ledger_mismatch')
 if response['status']!=200 or decoded['response']['numFound']!=58 or decoded['response']['start']!=12 or len(decoded['response']['docs'])!=46:raise ValueError('response_mismatch')
 query=json.loads(request['body_raw'])[0]
 if query['auth_key']!='[REDACTED_PUBLIC_CLIENT_KEY]' or query['q']!='S10D45' or query['start']!=12 or query['rows']!=200:raise ValueError('request_mismatch')
 if request['cookie_header_present'] or 'Authorization' in request['headers']:raise ValueError('header_mismatch')
 if sha(response['body_raw'].encode())!=response['body_sha256']:raise ValueError('response_hash_mismatch')
 probe_ledger=json.loads(probe['live/ledger.json'])
 seed_attempt=next(a for a in probe_ledger['attempts'] if a['phase']=='base' and a['category_key']=='S10D45')
 seed_record=json.loads(probe['live/'+seed_attempt['response_file']]);seed=json.loads(seed_record['body_raw'])['response']['docs'];current=decoded['response']['docs']
 seed_ids={str(x['pid']) for x in seed}; current_ids={str(x['pid']) for x in current}; repeated=sorted(seed_ids&current_ids);union=seed_ids|current_ids
 if repeated!=['507265'] or len(union)!=57:raise ValueError('cross_time_overlap_mismatch')
 discovery=json.load(open(PROBE_EVIDENCE))
 plan=[]
 for row in discovery['catalog']['root_plan']:
  if row['category_key']=='G10D03' or row['num_found']==0:continue
  offsets=list(range(0,row['num_found'],200))
  plan.append({'category_key':row['category_key'],'name':row['name'],'num_found':row['num_found'],'offsets':offsets,'requests_per_club':len(offsets)})
 per_club=sum(x['requests_per_club'] for x in plan)
 if per_club!=25:raise ValueError('revised_plan_mismatch')
 return {
  'schema_version':1,
  'raw_archive_sha256':sha(archive),
  'linked_discovery_probe_sha256':PROBE_SHA,
  'attempt':{
   'endpoint':'https://www.pricesmart.com/api/br_discovery/getProductsByKeyword','club':'6603','category_key':'S10D45','start':12,'rows':200,'post_attempts':1,'http_200':1,'retries':0,'returned_documents':46,'accepted_pages':0,'elapsed_seconds':ledger['elapsed_seconds'],'response_body_sha256':response['body_sha256'],'aborted_reason':ledger['aborted_reason'],'turso_operations':0,
  },
  'failure_evidence':{
   'seed_products':12,'continuation_products':46,'repeated_product_ids':repeated,'combined_unique_products':len(union),'expected_products':58,'missing_identity_count':1,'cause':'ranking_changed_between_probe_and_full_windows','partial_probe_windows_reusable_for_completeness':False,'whole_alimentos_snapshot_reusable':True,
  },
  'revised_plan':{
   'rows':200,'roots_nonempty':23,'root_windows':plan,'sps_base_requests':per_club,'florencia_base_requests':per_club,'new_base_requests':per_club*2,'prior_consumed_attempts':1,'accepted_prior_pages':0,'retry_reserve':5,'additional_post_attempts_max':per_club*2+5,'global_post_attempts_max':1+per_club*2+5,'accepted_documents_expected':1653*2,'discarded_documents_already_returned':46,'global_documents_returned_max':46+1653*2,'concurrency':1,'maximum_duration_seconds':600,'alimentos_recrawl_requests':0,'stop_if_num_found_changes':True,'requires_authorization_extension':True,
  },
  'decision':{'full_complete':False,'general_catalog_complete':False,'next_gate':'authorize revised non-reuse full budget'},
 }

def main():
 observed=reproduce();expected=json.load(open(REPORT/'evidence.json'))
 if observed!=expected:raise SystemExit('evidence_mismatch')
 print('PriceSmart remaining-full fail-closed evidence: OK')
if __name__=='__main__':main()
