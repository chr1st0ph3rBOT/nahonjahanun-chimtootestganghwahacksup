#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pipeline_nmap.py
#
# 기능:
# - (A) 제너레이터 JSON 모드: tools_0.2.1.json_test_.py가 출력한 JSON을 ingest
# - (B) XML 모드: nmap XML을 파싱하여 ingest
#
# 공통:
# - envelope 생성(_schema/_id/observed_at/source/payload)
# - knowledge.jsonl에 append 저장 + knowledge.db에 UPSERT
# - 콘솔 요약 출력
#
# 사용 예시
# (A-1) 제너레이터 실행 결과를 파이프로 연결:
#   python tools_0.2.1.json_test_.py | python pipeline_nmap.py --from-generator -
# (A-2) 제너레이터 결과를 파일로 저장 후:
#   python tools_0.2.1.json_test_.py > samples.json
#   python pipeline_nmap.py --from-generator samples.json
# (B) XML 파일 파싱:
#   python pipeline_nmap.py --from-xml scan.xml --command "nmap -sS -sV -p 80,443 example.com"
#
import argparse, datetime, hashlib, json, os, sqlite3, sys
from typing import List, Dict, Any, Optional
from xml.etree import ElementTree as ET

# ----------------------------
# 공용 유틸
# ----------------------------
def append_jsonl(envelope: dict, path: str = "knowledge.jsonl"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(envelope, ensure_ascii=False) + "\n")

def upsert_sqlite(envelope: dict, db_path: str = "knowledge.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS records(
        id TEXT PRIMARY KEY,
        schema TEXT,
        observed_at TEXT,
        command TEXT,
        payload TEXT
      )
    """)
    cur.execute("""
      INSERT INTO records(id, schema, observed_at, command, payload)
      VALUES(?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET
        schema=excluded.schema,
        observed_at=excluded.observed_at,
        command=excluded.command,
        payload=excluded.payload
    """, (
        envelope["_id"],
        envelope["_schema"],
        envelope["observed_at"],
        envelope["source"]["command"],
        json.dumps(envelope["payload"], ensure_ascii=False)
    ))
    conn.commit()
    conn.close()

def make_id(payload: dict, source: dict) -> str:
    """payload 핵심 + source 일부로 멱등 ID 생성"""
    core = {
        "scan_type": payload.get("scan_type"),
        "targets": payload.get("targets"),
        "results": payload.get("results"),
    }
    core_json = json.dumps(core, ensure_ascii=False, sort_keys=True)
    meta_json = json.dumps(
        {"command": source.get("command"), "args": source.get("args")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256((core_json + meta_json).encode("utf-8")).hexdigest()

def build_envelope(payload: dict, source: dict, schema: str = "network.nmap.v1") -> dict:
    return {
        "_schema": schema,
        "_id": make_id(payload, source),
        "observed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source": source,
        "payload": payload,
        "_parser": {"name": "nmap_ingest", "version": "1.1.0"},
    }

# ----------------------------
# (A) 제너레이터 JSON 모드
# ----------------------------
def normalize_targets(val: Optional[str]) -> List[str]:
    if not val:
        return []
    # 공백 구분 문자열 → 리스트
    return [t for t in str(val).split() if t.strip()]

def payload_from_generator_item(item: Dict[str, Any]) -> dict:
    """
    tools_0.2.1.json_test_.py의 한 항목:
      {"action": "...", "args": {...}, "command": "..."}
    를 payload 스켈레톤으로 변환
    """
    action = item.get("action")
    args = item.get("args", {}) or {}
    targets = normalize_targets(args.get("targets"))
    # targets를 제외한 나머지를 params로
    params = {k: v for k, v in args.items() if k != "targets"}
    payload = {
        "scan_type": action,
        "targets": targets,
        "params": params,
        "results": [],            # 아직 실행 결과 없음
        "extras": {"planned": True},
    }
    return payload

def ingest_generator_json(objs: List[Dict[str, Any]], out_jsonl: str, out_db: str):
    for i, item in enumerate(objs, 1):
        # source 메타: command는 문자열, args는 원본 args
        source = {
            "command": item.get("command") or "nmap",
            "args": item.get("args", {}),
            "host": os.uname().nodename if hasattr(os, "uname") else "local",
            "cwd": os.getcwd(),
            "raw_path": "(generator-json)"
        }
        payload = payload_from_generator_item(item)
        env = build_envelope(payload, source, schema="network.nmap.plan.v1")
        append_jsonl(env, out_jsonl)
        upsert_sqlite(env, out_db)
        print(f"[{i}] _id={env['_id']}  type={payload['scan_type']}  targets={payload['targets']}")

# ----------------------------
# (B) XML 모드
# ----------------------------
def parse_nmap_xml(raw_xml: str) -> dict:
    root = ET.fromstring(raw_xml)
    results = []
    for host in root.findall("host"):
        # address
        addr = None
        for a in host.findall("address"):
            if a.get("addrtype") in ("ipv4", "ipv6", None):
                addr = a.get("addr"); break
        # state
        st_el = host.find("status")
        state = st_el.get("state") if st_el is not None else None
        # hostname
        hn_el = host.find("hostnames/hostname")
        hostname = hn_el.get("name") if hn_el is not None else None
        # ports
        ports = []
        for p in host.findall("ports/port"):
            portnum = int(p.get("portid"))
            proto = p.get("protocol")
            ps = p.find("state")
            state_p = ps.get("state") if ps is not None else None
            svc_el = p.find("service")
            service = svc_el.get("name") if svc_el is not None else None
            product = svc_el.get("product") if svc_el is not None else None
            version = svc_el.get("version") if svc_el is not None else None
            scripts = [{"id": s.get("id"), "output": s.get("output")} for s in p.findall("script")]
            ports.append({
                "port": portnum, "proto": proto, "state": state_p,
                "service": service, "product": product, "version": version,
                "scripts": scripts or None
            })
        results.append({
            "address": addr, "state": state, "hostname": hostname,
            "ports": ports
        })
    # XML엔 커맨드/파라미터 정보가 없을 수 있어 스켈레톤만
    payload = {
        "scan_type": "unknown",
        "targets": [],
        "params": {},
        "results": results,
        "extras": {}
    }
    return payload

def ingest_xml_file(xml_path: str, command_str: str, out_jsonl: str, out_db: str):
    with open(xml_path, "r", encoding="utf-8") as f:
        raw = f.read()
    payload = parse_nmap_xml(raw)
    source = {
        "command": command_str or "nmap",
        "args": {},  # 알 수 없으면 빈 dict
        "host": os.uname().nodename if hasattr(os, "uname") else "local",
        "cwd": os.getcwd(),
        "raw_path": xml_path
    }
    env = build_envelope(payload, source, schema="network.nmap.v1")
    append_jsonl(env, out_jsonl)
    upsert_sqlite(env, out_db)
    print(f"XML -> _id={env['_id']} results_hosts={len(payload.get('results', []))}")

# ----------------------------
# main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--from-generator", metavar="PATH_OR_-",
                   help="tools_0.2.1.json_test_.py 출력(JSON). 파일 경로 또는 '-'(stdin)")
    g.add_argument("--from-xml", metavar="XML_PATH",
                   help="nmap XML 파일 경로")

    ap.add_argument("--command", default="", help="[XML 모드] 원 실행 커맨드 문자열 기록용")
    ap.add_argument("--out-jsonl", default="knowledge.jsonl")
    ap.add_argument("--out-db", default="knowledge.db")
    args = ap.parse_args()

    if args.from_generator:
        # 파일 또는 표준입력에서 JSON 읽기
        if args.from_generator == "-":
            data = sys.stdin.read()
        else:
            with open(args.from_generator, "r", encoding="utf-8") as f:
                data = f.read()
        objs = json.loads(data)
        if isinstance(objs, dict):
            objs = [objs]
        if not isinstance(objs, list):
            raise ValueError("제너레이터 JSON은 리스트여야 합니다.")
        ingest_generator_json(objs, args.out_jsonl, args.out_db)
    else:
        ingest_xml_file(args.from_xml, args.command, args.out_jsonl, args.out_db)

if __name__ == "__main__":
    main()
