# error_detector_status.py
'''
사용 방법 예시 코드:
from error_detector_basic import ErrorDetector
detector = ErrorDetector()

# subprocess 실행 예시
proc = subprocess.run(cmd, capture_output=True, text=True)
exec_meta = {"returncode": proc.returncode, "stderr": proc.stderr}

is_error = detector.detect(exec_meta)
if is_error:
    print("⚠️ 에러 발생:", exec_meta)
else:
    print("✅ 정상 실행 완료")

'''
from typing import Dict

class ErrorDetector:
    """Nmap 실행 결과의 exit status만으로 일반 오류를 판단하는 모듈"""

    def detect(self, exec_meta: Dict[str, any]) -> bool:
        """
        exec_meta 예시:
        {
            "returncode": 0,  # subprocess.run().returncode
        }

        반환값:
          True  -> 에러 발생
          False -> 정상
        """
        rc = exec_meta.get("returncode", None)

        # returncode가 존재하지 않으면 비정상 실행으로 판단
        if rc is None:
            return True

        # 0이 아니면 에러
        if rc != 0:
            return True

        # 0이면 정상
        return False


if __name__ == "__main__":
    detector = ErrorDetector()

    # === 테스트 예시 ===
    case1 = {"returncode": 0}
    case2 = {"returncode": 1}
    case3 = {"returncode": None}

    print("정상 케이스 →", detector.detect(case1))      # False
    print("에러 케이스(returncode=1) →", detector.detect(case2))  # True
    print("에러 케이스(None) →", detector.detect(case3))           # True
