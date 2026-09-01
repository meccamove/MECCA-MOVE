#!/usr/bin/env python3
# MECCA MOVE - LH bulk floorplan collector
import re, json, time, hashlib
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE="https://apply.lh.or.kr"
LIST=BASE+"/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026"
LISTS=[
 BASE+"/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026",
 BASE+"/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1027",
 BASE+"/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1028"
]
OUT=Path(__file__).resolve().parent/"data"
OUT.mkdir(exist_ok=True)
DB=OUT/"verified_floorplans_cumulative.json"
STATE=OUT/"collector_state.json"

session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 MECCA-MOVE-Floorplan-Indexer/1.0"})

def norm(s):
    return re.sub(r"\s+"," ",(s or "")).strip()

def load_db():
    if DB.exists():
        x=json.loads(DB.read_text(encoding="utf-8"))
        return x.get("records",[])
    return []

def save(records):
    # Deduplicate by official source + complex name
    uniq={}
    for r in records:
        key=(r.get("source"),r.get("name"))
        uniq[key]=r
    records=list(uniq.values())
    for i,r in enumerate(records,1):
        r["id"]=f"MECCA-REAL-{i:07d}"
    DB.write_text(json.dumps({
        "version":"auto-collector-v1",
        "verified_source_record_count":len(records),
        "records":records
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return len(records)

def get(url, params=None):
    r=session.get(url,params=params,timeout=30)
    r.raise_for_status()
    return r

def notice_links(html):
    soup=BeautifulSoup(html,"html.parser")
    found=set()
    for a in soup.find_all("a",href=True):
        h=a["href"]
        if "selectWrtancInfo.do" in h and "panId=" in h:
            found.add(urljoin(BASE,h))
    # LH sometimes stores URLs in onclick/javascript.
    for m in re.findall(r'[^"\\']*selectWrtancInfo\.do\?[^"\\']*panId=[^"\\'&\\s]+[^"\\']*',html):
        if m.startswith("http"): found.add(m)
        else: found.add(urljoin(BASE,m))
    return sorted(found)

def parse_notice(url, html):
    soup=BeautifulSoup(html,"html.parser")
    text=norm(soup.get_text(" "))
    # Only keep notices that explicitly expose floorplan assets/content.
    floorplan = ("평면도" in text)
    if not floorplan: return []

    attachment_names=[]
    for a in soup.find_all("a"):
        t=norm(a.get_text(" "))
        if "평면도" in t or ("팸플릿" in t and (".zip" in t.lower() or ".pdf" in t.lower())):
            attachment_names.append(t)

    # Supply complex headings are followed by 소재지/전용면적 in LH rendered HTML.
    pat=re.compile(r'([가-힣A-Za-z0-9()·\\-\\s]+?)\\s+소재지\\s*:\\s*([^\\n]{5,120}?)\\s+전용면적\\(㎡\\)\\s*:\\s*([0-9.]+)\\s*~\\s*([0-9.]+)')
    rows=[]
    for m in pat.finditer(soup.get_text("\n")):
        name=norm(m.group(1).split("\n")[-1])
        road=norm(m.group(2))
        if len(name)<2: continue
        rows.append({
            "agency":"LH","name":name,"road":road,
            "area_range_m2":[float(m.group(3)),float(m.group(4))],
            "types":[],"floorplan_available":True,
            "attachment":attachment_names[:10],
            "source":url,"verified":True,
            "status":"auto_source_verified","verified_at":time.strftime("%Y-%m-%d")
        })

    # If structured extraction fails, retain notice as a source record, not a fake complex.
    if not rows:
        title=norm((soup.find("h3") or soup.find("title")).get_text(" ")) if (soup.find("h3") or soup.find("title")) else "LH 평면도 공고"
        rows=[{
            "agency":"LH","name":title,"road":None,"types":[],
            "floorplan_available":True,"attachment":attachment_names[:10],
            "source":url,"verified":True,"status":"auto_verified_notice_asset",
            "verified_at":time.strftime("%Y-%m-%d"),
            "verification_scope":"official LH notice containing floorplan content; complex fields pending extraction"
        }]
    return rows

def crawl(max_pages=2000, sleep=0.25):
    # First ingest official seed URLs already verified by MECCA.
    seed_file=OUT/"official_seed_urls.json"
    seed_urls=[]
    if seed_file.exists():
        seed_urls=json.loads(seed_file.read_text(encoding="utf-8")).get("verified_official_urls",[])

    records=load_db()
    seen_urls={r.get("source") for r in records}
    for u in seed_urls:
        if u in seen_urls: continue
        try:
            rr=get(u); rows=parse_notice(u,rr.text)
            records.extend(rows); seen_urls.add(u); save(records)
        except Exception as e:
            print("SEED SKIP",u,e)
    scanned=0; added=0
    for page in range(1,max_pages+1):
        # Sweep all configured LH housing notice lists on each page.
        html_parts=[]
        for list_url in LISTS:
            try:
                html_parts.append(get(list_url,params={"pageIndex":page}).text)
            except Exception as e:
                print("LIST SKIP",list_url,e)
        class _R: pass
        r=_R(); r.text="\n".join(html_parts)
        links=notice_links(r.text)
        if not links and page>20: break
        for u in links:
            scanned+=1
            if u in seen_urls: continue
            try:
                rr=get(u)
                rows=parse_notice(u,rr.text)
                records.extend(rows); added+=len(rows); seen_urls.add(u)
                save(records)
            except Exception as e:
                print("SKIP",u,e)
            time.sleep(sleep)
        STATE.write_text(json.dumps({"page":page,"scanned":scanned,"added":added,"total":len(records),"seed_count":len(seed_urls)},ensure_ascii=False,indent=2),encoding="utf-8")
    total=save(records)
    print(json.dumps({"scanned":scanned,"added":added,"total":total},ensure_ascii=False))

if __name__=="__main__":
    crawl()
