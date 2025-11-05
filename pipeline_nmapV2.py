#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_nmapV2.py
- nmap 일반 출력(-oN) 파일을 파싱해 JSON 지식 스토리지로 저장
- 윈도우/맥/리눅스 공통 동작, 경로는 현재 작업폴더 기준
- 샘플 출력 생성 옵션(--make-samples) 포함 (nmap 미설치 상태에서도 파서 테스트 가능)

사용 예)
  # 1) 샘플 출력 생성 + 파싱 -> output/nmap_knowledge.json
  python pipeline_nmapV2.py --make-samples

  # 2) 실제 nmap -oN 파일 여러 개 파싱
  python pipeline_nmapV2.py scans/host_discovery.txt scans/service_version.txt

  # 3) 출력 파일 위치 변경
  python pipeline_nmapV2.py scans/*.txt --out output/my_knowledge.json
"""

from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# ---------- 파서: nmap -oN 일반 텍스트 -> 구조화 ----------
HOST_HDR_RE     = re.compile(r"^Nmap scan report for (.+)$")
HOST_UP_RE      = re.compile(r"^Host is up")
PORT_HEADER_RE  = re.compile(r"^\s*PORT\s+STATE\s+SERVICE", re.I)
PORT_LINE_RE    = re.compile(r"^\s*(\d+)\/(tcp|udp)\s+(\S+)\s+(\S+)(?:\s+(.*))?$")
SERVICE_INFO_RE = re.compile(r"^Service Info:\s*(.+)$", re.I)
OS_DEVICE_RE    = re.compile(r"^Device type:\s*(.+)$", re.I)
OS_RUNNING_RE   = re.compile(r"^Running:\s*(.+)$", re.I)
OS_DETAILS_RE   = re.compile(r"^OS details:\s*(.+)$", re.I)
SCRIPT_LINE_RE  = re.compile(r"^\s*\|[_ ]?([^:]+):\s*(.*)$")  # "|_banner: ..." 또는 "| banner: ..."
START_META_RE   = re.compile(r"^# Nmap .* initiated .* as: (.+)$")

def _split_name_ip(header: str) -> (Optional[str], Optional[str]):
    # "example.com (203.0.113.5)" 또는 "203.0.113.5" 형태 처리
    if "(" in header and header.endswith(")"):
        name, ip = header.rsplit("(", 1)
        return name.strip(), ip[:-1].strip()
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", header):
        return None, header.strip()
    return header.strip(), None

def parse_nmap_text(text: str, source: str = "") -> Dict:
    """
    nmap -oN 일반 출력 하나를 다음 스키마로 변환:
    {
      "source": "파일명 또는 태그",
      "scan": {"cmdline": "..."},
      "hosts": [
        {
          "hostname": "...?", "ip": "x.x.x.x", "status": "up|down|unknown",
          "ports": [
            {"port": 22, "proto": "tcp", "state": "open", "service": "ssh",
             "product": "OpenSSH 8.2p1 Ubuntu ..."}
          ],
          "os": {"device_type": "...", "running": "...", "details": "..."},
          "service_info": "OS: Linux; CPE: ...",
          "scripts": {"banner": "Apache/2.4.29 ...", "ssh-hostkey": "..."}
        }
      ]
    }
    """
    lines = text.splitlines()
    out = {"source": source, "scan": {}, "hosts": []}

    # 1) 상단 메타(실행 커맨드)
    for ln in lines[:10]:
        m = START_META_RE.match(ln.strip())
        if m:
            out["scan"]["cmdline"] = m.group(1).strip()
            break

    cur = None
    in_ports = False

    for ln in lines:
        s = ln.rstrip("\n")

        # 새 호스트 시작
        m = HOST_HDR_RE.match(s)
        if m:
            if cur:
                out["hosts"].append(cur)
            hostname, ip = _split_name_ip(m.group(1))
            cur = {
                "hostname": hostname,
                "ip": ip,
                "status": "unknown",
                "ports": [],
                "os": {},
                "service_info": None,
                "scripts": {}
            }
            in_ports = False
            continue

        if not cur:
            continue

        # 호스트 상태
        if HOST_UP_RE.match(s):
            cur["status"] = "up"
            continue

        # 포트 테이블 진입
        if PORT_HEADER_RE.match(s):
            in_ports = True
            continue

        # 포트 테이블 내용
        if in_ports:
            if not s.strip() or not re.match(r"^\s*\d", s):  # 빈 줄 또는 포트라인 아님
                in_ports = False
            else:
                pm = PORT_LINE_RE.match(s)
                if pm:
                    port = int(pm.group(1))
                    proto = pm.group(2)
                    state = pm.group(3)
                    service = pm.group(4)
                    rest = (pm.group(5) or "").strip()  # 제품/버전 등
                    cur["ports"].append({
                        "port": port,
                        "proto": proto,
                        "state": state,
                        "service": service,
                        "product": rest or None
                    })
                continue

        # OS / Service Info
        dm = OS_DEVICE_RE.match(s)
        if dm:
            cur["os"]["device_type"] = dm.group(1).strip()
            continue
        rm = OS_RUNNING_RE.match(s)
        if rm:
            cur["os"]["running"] = rm.group(1).strip()
            continue
        odm = OS_DETAILS_RE.match(s)
        if odm:
            cur["os"]["details"] = odm.group(1).strip()
            continue
        sim = SERVICE_INFO_RE.match(s)
        if sim:
            cur["service_info"] = sim.group(1).strip()
            continue

        # Host script results 섹션 라인들 처리 (| 또는 |_ 로 시작)
        sm = SCRIPT_LINE_RE.match(s)
        if sm:
            k = sm.group(1).strip()
            v = sm.group(2).strip()
            cur["scripts"][k] = v
            continue

    if cur:
        out["hosts"].append(cur)
    return out

# ---------- 샘플 출력(오프라인 테스트용) ----------
SAMPLES: Dict[str, str] = {
    "host_discovery.txt": """# Nmap 7.93 scan initiated Fri Oct 24 12:00:00 2025 as: nmap -sn 192.0.2.0/30 -T4 -oN host_discovery.txt
Nmap scan report for 192.0.2.1
Host is up (0.022s latency).
Nmap scan report for 192.0.2.2
Host is up (0.045s latency).
Nmap done: 4 IP addresses (2 hosts up) scanned in 2.47 seconds
""",
    "tcp_syn_top.txt": """# Nmap 7.93 scan initiated Fri Oct 24 12:01:00 2025 as: nmap -sS --top-ports 100 198.51.100.10 -T3 -oN tcp_syn_top.txt
Nmap scan report for example.test (198.51.100.10)
Host is up (0.018s latency).
Not shown: 97 closed ports
PORT    STATE SERVICE
22/tcp  open  ssh
80/tcp  open  http
443/tcp open  https
8080/tcp closed http-proxy
Nmap done: 1 IP address (1 host up) scanned in 5.42 seconds
""",
    "service_version.txt": """# Nmap 7.93 scan initiated Fri Oct 24 12:02:00 2025 as: nmap -sS -sV -p 22,80,443 203.0.113.5 -T3 -oN service_version.txt
Nmap scan report for 203.0.113.5
Host is up (0.030s latency).

PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.3 (protocol 2.0)
80/tcp  open  http    Apache httpd 2.4.41 ((Ubuntu))
443/tcp open  https   nginx 1.18.0
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 3.34 seconds
""",
    "os_detect.txt": """# Nmap 7.93 scan initiated Fri Oct 24 12:03:00 2025 as: nmap -A -p 22,80 --script=banner 198.51.100.20 -oN os_detect.txt
Nmap scan report for 198.51.100.20
Host is up (0.050s latency).

PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Debian 4
80/tcp open  http    Apache httpd 2.4.29

Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel
OS details: Linux 3.10 - 4.15
Network Distance: 1 hop

Host script results:
|_banner: Apache/2.4.29 (Debian)
|_ssh-hostkey: SSH-2.0-OpenSSH_7.6p1 Debian-4

Nmap done: 1 IP address (1 host up) scanned in 8.01 seconds
"""
}

def write_samples(folder: Path) -> List[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, txt in SAMPLES.items():
        p = folder / name
        p.write_text(txt, encoding="utf-8")
        paths.append(p)
    return paths

# ---------- 진입점 ----------
def main():
    ap = argparse.ArgumentParser(description="Parse nmap -oN outputs to JSON knowledge storage.")
    ap.add_argument("inputs", nargs="*", help="nmap -oN 출력 파일 경로(여러 개 가능)")
    ap.add_argument("--out", default="output/nmap_knowledge.json", help="저장할 JSON 경로 (기본: output/nmap_knowledge.json)")
    ap.add_argument("--make-samples", action="store_true", help="샘플 nmap 출력 파일을 ./samples 폴더에 생성하고 그것들을 파싱")
    args = ap.parse_args()

    inputs: List[Path] = [Path(p) for p in args.inputs]
    if args.make_samples:
        samples_dir = Path("samples")
        print(f"[+] 샘플 출력 생성: {samples_dir.resolve()}")
        inputs = write_samples(samples_dir)

    if not inputs:
        print("(!) 입력 파일이 없습니다. 파일 경로를 주거나 --make-samples 옵션을 사용하세요.")
        return

    # 출력 경로 보장
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 파일별 파싱
    bundle = {
        "schema_version": "1.0",
        "source_files": [],
        "results": []  # 파일 단위 결과
    }

    for path in inputs:
        if not path.exists():
            print(f"[!] 파일 없음: {path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_nmap_text(text, source=str(path))
        bundle["source_files"].append(str(path))
        bundle["results"].append(parsed)

    # 저장 (ensure_ascii=False로 한글/기호 보존)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)

    print(f"[✓] JSON 저장 완료: {out_path.resolve()}")
    print(f"    - 파일 수: {len(bundle['source_files'])}")
    # 간단 요약
    total_hosts = sum(len(r.get("hosts", [])) for r in bundle["results"])
    print(f"    - 총 호스트: {total_hosts}")

if __name__ == "__main__":
    main()
