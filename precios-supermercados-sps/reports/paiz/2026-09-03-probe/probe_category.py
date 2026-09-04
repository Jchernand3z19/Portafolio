#!/usr/bin/env python3
"""Prove the category-1 path and page size for the two active TGU Paiz contexts."""
from __future__ import annotations
import base64, hashlib, json, time, urllib.request
from pathlib import Path
from urllib.parse import urlencode

BASE='https://www.paiz.com.hn'
SC='2'
STORES={'walmarthnsp633':2060,'walmarthnsp4010':2025}
UA='Mozilla/5.0 (compatible; PreciosSupermercadosSPS-PaizCategory/1.0; read-only)'

def rid(s): return base64.b64encode(('SW#'+s).encode()).decode()

def main():
    root=Path('paiz-category-artifact'); raw=root/'raw'; raw.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,(seller,expected) in enumerate(STORES.items(),1):
        path=f'/api/io/_v/api/intelligent-search/product_search/accesscontrollist/{seller}/category-1/abarrotes'
        q={'regionId':rid(seller),'sc':SC,'country':'HND','count':'100','page':'1'}
        url=BASE+path+'?'+urlencode(q)
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'},method='GET')
        started=time.time()
        with urllib.request.urlopen(req,timeout=30) as response:
            body=response.read(); status=response.status
            headers={k.lower():v for k,v in response.headers.items() if k.lower()!='set-cookie'}
        doc=json.loads(body); filename=f'{i:02d}-{seller}-abarrotes.body'; (raw/filename).write_bytes(body)
        row={'index':i,'seller':seller,'status':status,'url':url,'elapsed_seconds':round(time.time()-started,3),
             'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'recordsFiltered':doc.get('recordsFiltered'),
             'products':len(doc.get('products',[])),'operator':doc.get('operator'),'fuzzy':doc.get('fuzzy'),
             'pagination':doc.get('pagination'),'content_type':headers.get('content-type'),'file':'raw/'+filename}
        print(json.dumps(row,ensure_ascii=False,sort_keys=True)); rows.append(row)
        if status!=200 or row['recordsFiltered']!=expected or row['products']!=100:
            raise SystemExit(f'category_contract_failed:{row}')
    evidence={'request_count':len(rows),'retry_count':0,'concurrency':1,'category_key':'category-1','category_value':'abarrotes','rows':rows}
    (root/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2),encoding='utf-8')
if __name__=='__main__': main()
