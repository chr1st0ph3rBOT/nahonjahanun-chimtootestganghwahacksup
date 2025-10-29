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
