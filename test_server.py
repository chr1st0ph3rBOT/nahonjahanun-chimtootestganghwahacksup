# practice_server.py
# Python 3.8+
# 사용법: FLAG 값을 바꾸려면 --flag "FLAG{your_flag}" 로 실행하거나
# 환경변수 FLAG로 지정 가능: FLAG="FLAG{...}" python3 practice_server.py

import os
import threading
import socket
import argparse
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "<h3>연습 서버에 오신 걸 환영합니다.</h3><p>nmap으로 네트워크 서비스들을 스캔해보세요.</p>"

def run_flask(host="0.0.0.0", port=8080):
    # 디버그 모드 끄고 로컬에서만 실행 권장
    app.run(host=host, port=port, debug=False, use_reloader=False)

def banner_service(host="0.0.0.0", port=31337, banner_text=None):
    """
    단순 TCP 배너 서비스 — 연결 즉시 배너(여기에 FLAG 포함)를 송신하고 연결 종료.
    nmap의 버전 탐지/배너 스크립트로 읽을 수 있도록 설계.
    """
    if banner_text is None:
        banner_text = "MY_FAKE_SERVICE 1.0\n"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    print(f"[banner_service] Listening on {host}:{port}")
    try:
        while True:
            conn, addr = sock.accept()
            with conn:
                print(f"[banner_service] Connection from {addr}")
                # 배너는 바이트로 전송. 끝에 newline을 포함시키면 nmap이 읽기 편함.
                try:
                    conn.sendall(banner_text.encode("utf-8"))
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("[banner_service] Stopping.")
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser(description="Practice server (Flask + TCP banner service)")
    parser.add_argument("--flag", type=str, default=os.environ.get("FLAG", "FLAG{example_flag}"),
                        help="FLAG string to expose in the banner service")
    parser.add_argument("--http-port", type=int, default=8080, help="Flask HTTP port")
    parser.add_argument("--banner-port", type=int, default=31337, help="TCP banner port")
    args = parser.parse_args()

    # 배너에 포함될 텍스트: 서비스 식별 후 FLAG
    banner_text = f"MY_FAKE_SERVICE 1.0\n{args.flag}\n"

    # Flask와 배너 서비스를 각각 스레드로 띄움
    t1 = threading.Thread(target=run_flask, kwargs={"host":"0.0.0.0", "port": args.http_port}, daemon=True)
    t2 = threading.Thread(target=banner_service, kwargs={"host":"0.0.0.0", "port": args.banner_port, "banner_text": banner_text}, daemon=True)

    t1.start()
    t2.start()

    print(f"[main] Flask on port {args.http_port}, Banner on port {args.banner_port}")
    print("[main] 서버가 실행 중입니다. 중지하려면 Ctrl+C")

    try:
        # 메인 스레드 대기
        while True:
            t1.join(timeout=1)
            t2.join(timeout=1)
    except KeyboardInterrupt:
        print("\n[main] 종료 신호 수신 — 정리 후 종료합니다.")

if __name__ == "__main__":
    main()
