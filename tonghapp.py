import hashlib
import hmac



def flag_reward(flag_str, known_flags, big_reward=1000.0):
    """
    플래그 정답 여부에 따른 스칼라 보상 계산 함수 (순수 함수)
    
    파라미터:
    - flag_str     : (str) 제출/발견된 플래그 원문
    - known_flags  : (dict) {"FLAG": "<sha256_hex>"}  (정답 해시 딕셔너리)
    - big_reward   : (float) 정답시 지급 보상 크기 (기본 1000.0)
    
    반환값:
    - reward       : (float) 정답 시 big_reward, 아니면 0.0
    """

    # 입력 검증
    if not isinstance(flag_str, str):
        return 0.0

    # 제출 플래그 해시 계산
    submitted_hash = hashlib.sha256(flag_str.strip().encode("utf-8")).hexdigest()

    # 등록된 정답 해시 확인
    try:
        expected_key, expected_hash = next(iter(known_flags.items()))
    except StopIteration:
        return 0.0

    # 안전 비교
    is_correct = hmac.compare_digest(submitted_hash, expected_hash)

    # 보상 산출 (오직 정답만 지급, 외부 상태 미변경)
    reward = float(big_reward) if is_correct else 0.0

    # [PARSE_HOOK]  
    # 필요하면 여기서 플래그 내 추가 메타데이터(REWARD= 등) 파싱 확장
    # 예시:
    #   parsed_reward = parse_reward_from_string(flag_str)
    #   if is_correct and parsed_reward is not None:
    #       reward += float(parsed_reward)

    return reward


#에러기반
import re

#  오류 유형별 penalty 상수 선언
PENALTY_DICT = {
    'hostname_resolution_error':   -0.2,  # 호스트 이름 해석 실패
    'device_access_error':         -0.3,  # 장치 접근 권한/불가
    'network_unreachable':         -0.25, # 대상 네트워크 접근 불가
    'invalid_target':              -0.15, # 입력 타겟값 부적절
    'nmap_internal_error':         -0.4   # 내부 오류(비정상 종료 등)
}
MIN_REWARD = -1.0  # 최저 보상값 (절대치)
MAX_REWARD = 1.0   # 최고 보상값

def error(output_log):
    """
    nmap 실행 중 발생한 오류 메시지를 분석하고,
    자동으로 수정 가능한 경우 대응 조치를 제안하거나 보정한다.

    Parameters:
    - output_log (str): nmap 실행 결과 로그 문자열

    Returns:
    - dict: {
        'error_detected': bool,      # 오류 존재 여부
        'error_type': str,           # 오류 유형 식별(키)
        'suggested_fix': str | None, # 제안된 수정 또는 재시도 방안
        'auto_fixable': bool         # 자동 수정 가능 여부
      }
    """
    result = {
        'error_detected': False,
        'error_type': None,
        'suggested_fix': None,
        'auto_fixable': False
    }
    log = output_log.lower()

    # 호스트 이름 해석 실패
    if re.search(r"(unable to resolve hostname|dns resolution failed|error resolving name)", log):
        result.update({
            'error_detected': True,
            'error_type': 'hostname_resolution_error',
            'suggested_fix': '대상 호스트 이름이 올바른지 확인하거나 IP 주소로 직접 입력하세요.',
            'auto_fixable': True
        })
    #  장치 접근 불가
    elif "failed to open device" in log:
        result.update({
            'error_detected': True,
            'error_type': 'device_access_error',
            'suggested_fix': '루트 권한으로 다시 실행하거나 네트워크 인터페이스 이름을 명시하세요. (예: nmap -e eth0 ...)',
            'auto_fixable': False
        })
    #  대상 접근 불가
    elif "no route to host" in log:
        result.update({
            'error_detected': True,
            'error_type': 'network_unreachable',
            'suggested_fix': '대상 네트워크 연결 상태를 점검하고, 방화벽 또는 VPN 설정을 확인하세요.',
            'auto_fixable': False
        })
    #  유효하지 않은 대상
    elif "not a valid target" in log:
        result.update({
            'error_detected': True,
            'error_type': 'invalid_target',
            'suggested_fix': '입력한 대상 형식(IP, CIDR 등)을 다시 확인하세요.',
            'auto_fixable': True
        })
    #  nmap 내부 오류 (일반적 종료)
    elif re.search(r"(nmap error|quitting)", log):
        result.update({
            'error_detected': True,
            'error_type': 'nmap_internal_error',
            'suggested_fix': 'nmap 명령 구문과 옵션을 다시 확인하거나 -d(디버그 모드)로 재실행하세요.',
            'auto_fixable': False
        })
    #  오류 없음
    else:
        result.update({
            'error_detected': False,
            'error_type': None,
            'suggested_fix': None,
            'auto_fixable': False
        })
    return result

def calc_penalty(log):
    """
    error() 함수로 식별된 오류 유형에 따라 해당 penalty만큼
    보상을 감소시키는 단일 책임 함수. 적용 penalty는 최저/최고 보상값 범위 내로 제한.
    """
    err = error(log)  # 오류 분석 실행
    # 오류 유형이 발견되면 PENALTY_DICT 값을 적용, 아니면 0(감점 없음)
    penalty = PENALTY_DICT.get(err['error_type'], 0.0)
    # 총 보상(예: 1.0에서 penalty만큼 빼기, 실제 시스템에서는 누적 보상/스텝별 반영)
    reward = max(MIN_REWARD, min(MAX_REWARD, 1.0 + penalty))
    # 상세 결과표와 계산된 보상 함께 반환
    return reward

# 예시 사용
log1 = "Nmap scan report: Unable to resolve hostname example.local"
print(calc_penalty(log1))

