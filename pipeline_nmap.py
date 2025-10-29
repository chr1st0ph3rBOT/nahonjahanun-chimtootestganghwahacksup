# simple_nmap_pipeline.py
# 기능:
# 1) 샘플 nmap XML 하나 파싱(아주 간단)
# 2) envelope 생성(_schema/_id/observed_at/source/payload)
# 3) JSONL에 append 저장 + SQLite에 "멱등 업서트(upsert)" 저장
# 4) 콘솔에 보기 좋게 출력

import json, hashlib, sqlite3, datetime, os
from xml.etree import ElementTree as ET

# ----------------------------
# 0) 샘플 nmap XML (그냥 예시)
# ----------------------------
SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sS -sV -p 80,443 example.com" start="1700000000">
  <host>
    <status state="up" />
    <address addr="93.184.216.34" addrtype="ipv4"/>
    <hostnames><hostname name="example.com"/></hostnames>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx" version="1.22"/>
        <script id="http-title" output="Example Domain"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https" product="nginx" version="1.22"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""

# -------------------------------------
# 1) 간단 파서: nmap XML -> payload(dict)
# -------------------------------------
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

    payload = {
        "scan_type": "service_version",        # 예시로 고정
        "targets": ["example.com"],            # 예시로 고정
        "params": {"ports": "80,443", "timing": "T3"},
        "results": results,
        "extras": {}
    }
    return payload

# ------------------------------------------------------
# 2) 멱등 ID 만들기: payload 핵심 + source 일부로 sha256
# ------------------------------------------------------
def make_id(payload: dict, source: dict) -> str:
    core = {
        "scan_type": payload.get("scan_type"),
        "targets": payload.get("targets"),
        "results": payload.get("results")
    }
    core_json = json.dumps(core, ensure_ascii=False, sort_keys=True)
    meta_json = json.dumps({"command": source.get("command"), "args": source.get("args")}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256((core_json + meta_json).encode("utf-8")).hexdigest()

# ------------------------------------------------------
# 3) JSONL에 append, SQLite에 UPSERT(멱등 업서트)
# ------------------------------------------------------
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

# ----------------------------
# 4) 메인: 실행하고 콘솔에 출력
# ----------------------------
def main():
    # 1) 파싱
    payload = parse_nmap_xml(SAMPLE_XML)

    # 2) 소스 메타(예시)
    source = {
        "command": "nmap",
        "args": ["-sS","-sV","-p","80,443","example.com"],
        "host": os.uname().nodename if hasattr(os, "uname") else "local",
        "cwd": os.getcwd(),
        "raw_path": "(inline-sample)"
    }

    # 3) envelope 조립
    envelope = {
        "_schema": "network.nmap.v1",
        "_id": make_id(payload, source),
        "observed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source": source,
        "payload": payload,
        "_parser": {"name": "nmap_xml", "version": "1.0.0"}
    }

    # 4) 저장
    append_jsonl(envelope, "knowledge.jsonl")
    upsert_sqlite(envelope, "knowledge.db")

    # 5) 콘솔 출력(요약 + 전체)
    print("\n[요약]")
    print(f"- _id: {envelope['_id']}")
    print(f"- 저장: knowledge.jsonl (append), knowledge.db (upsert)")
    print("\n[envelope 전체]")
    print(json.dumps(envelope, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
