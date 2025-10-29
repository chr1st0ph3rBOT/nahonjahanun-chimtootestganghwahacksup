import math
import re

# ========================================================
# 1. 자동 감쇠형 호기심 보상 함수 (로그 감쇠 방식)
# ========================================================

def curiosity_reward_decay(step, base_reward=1.0, decay_strength=0.1):  # 통합필요: step
    """
    호기심 보상을 로그 함수 형태로 감쇠시키는 함수.
    
    선형 감쇠보다 부드럽게 감소하며, 초반에는 천천히, 후반에도 완전히 0이 되지 않음.
    이를 통해 창의성을 계속 유지하면서도 점진적으로 exploitation 단계로 전환.
    
    수식: R_c(t) = base_reward / (1 + decay_strength * log(1 + step))
    
    Parameters:
    - step: 현재 스텝 수 (전체 에피소드 진행 정도)
    - base_reward: 초기 호기심 보상 값
    - decay_strength: 감쇠 강도 조절 파라미터 (클수록 빠르게 감소)
    
    Returns:
    - 감쇠된 호기심 보상 값
    """
    reward = base_reward / (1 + decay_strength * math.log1p(step))  # log1p(x) = log(1+x)
    return reward


# ========================================================
# 2. 음의 보상 포함형 호기심 보상 함수
# ========================================================

def curiosity_reward_with_penalty(is_redundant=False, is_error=False, is_critical=False,
                                  step=0, base_reward=1.0, decay_strength=0.1,  # 통합필요: step
                                  penalty_redundant=0.2, penalty_error=0.4, 
                                  penalty_critical=0.8):
    """
    로그 감쇠 + 조건부 음의 보상을 결합한 호기심 보상 함수.
    
    창의성과 탐색을 유지하되, 명백히 해로운 행동에만 패널티를 부여.
    
    Parameters:
    - is_redundant: 같은 행동 과도 반복 여부 (5회 이상)
    - is_error: 일반 오류 발생 여부
    - is_critical: 심각한 시스템 오류 발생 여부
    - step: 현재 스텝 수
    - base_reward: 기본 호기심 보상
    - decay_strength: 로그 감쇠 강도
    - penalty_redundant: 반복 행동 패널티
    - penalty_error: 일반 오류 패널티
    - penalty_critical: 심각한 오류 패널티
    
    Returns:
    - 최종 호기심 보상 (음수 가능)
    """
    # 기본 로그 감쇠 적용
    reward = base_reward / (1 + decay_strength * math.log1p(step))
    
    # 조건부 패널티 적용
    if is_redundant:
        reward -= penalty_redundant
    if is_error:
        reward -= penalty_error
    if is_critical:
        reward -= penalty_critical
    
    # 최소값 제한 (너무 큰 음의 보상 방지)
    return max(reward, -1.0)


# ========================================================
# 3. 음의 보상 조건 판별 함수 (완성판)
# ========================================================

def check_negative_reward_conditions(
        action_log,         # 통합필요: 지금까지 수행한 행동 리스트
        current_action,     # 통합필요: 현재 수행한 행동 (문자열)
        output_log,         # 통합필요: 툴 실행 후 출력 로그
        knowledge_gain,     # 통합필요: 이번 행동으로 얻은 정보량 (0~1)
        max_repeats=5,      # 반복 허용 횟수 (해킹은 재시도가 의미있을 수 있으므로 5회로 설정)
        min_info_gain=0.005,  # 정보 증가 최소 임계값 (너무 엄격하지 않게 낮춤)
        error_keywords=None,
        critical_error_keywords=None,
        system_keywords=None):
    """
    음의 보상 부여 조건을 정밀 감지하는 함수.
    
    해킹 특성상 같은 명령도 재시도 시 다른 결과가 나올 수 있으므로,
    과도한 제약을 피하고 '명백히 비효율적인 경우'에만 패널티 부여.
    
    Parameters:
    - action_log: 이전까지 수행된 모든 행동 리스트
    - current_action: 현재 시도한 행동
    - output_log: 명령 실행 후 출력된 로그 텍스트
    - knowledge_gain: 이번 행동을 통해 얻은 새로운 정보의 양 (0~1 스케일)
    - max_repeats: 동일 행동 반복 허용 횟수 (기본 5회)
    - min_info_gain: 의미 있는 정보 증가로 간주되는 최소값
    - error_keywords: 일반 오류 감지 키워드
    - critical_error_keywords: 치명적 오류 감지 키워드
    - system_keywords: 접근 제한 관련 키워드
    
    Returns:
    - dict: {
        'redundant': bool,      # 과도한 반복 여부
        'error': bool,          # 일반 오류 발생 여부
        'critical': bool,       # 심각한 오류 여부
        'inefficient': bool,    # 비효율적 탐색 여부
        'penalty_score': float  # 통합필요: 총 패널티 점수 (음수)
      }
    """
    
    # 기본 키워드 설정
    if error_keywords is None:
        error_keywords = [
            "error", "failed", "exception", "denied", "invalid", 
            "timeout", "refused", "not found"
        ]
    
    if critical_error_keywords is None:
        critical_error_keywords = [
            "segmentation fault", "core dumped", "crash", "fatal", 
            "terminated", "killed", "panic"
        ]
    
    if system_keywords is None:
        system_keywords = [
            "unauthorized", "access denied", "permission", "firewall",
            "blocked", "forbidden"
        ]
    
    # 결과 딕셔너리 초기화
    result = {
        'redundant': False,
        'error': False,
        'critical': False,
        'inefficient': False,
        'penalty_score': 0.0  # 통합필요: 다른 모듈에서 보상 계산에 사용
    }
    
    # ----------------------------------------
    # (1) 반복 행동 감지 - 5회 이상 반복 시만 패널티
    # ----------------------------------------
    repeat_count = action_log.count(current_action)
    if repeat_count >= max_repeats:
        result['redundant'] = True
        # 점진적 패널티: 반복 횟수가 늘수록 강화
        excess_repeats = repeat_count - max_repeats + 1
        result['penalty_score'] -= 0.15 * excess_repeats
    
    # ----------------------------------------
    # (2) 일반 오류 감지 - 출력 로그에서 오류 키워드 검색
    # ----------------------------------------
    error_found = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
        for kw in error_keywords
    )
    if error_found:
        result['error'] = True
        result['penalty_score'] -= 0.3
    
    # ----------------------------------------
    # (3) 심각한 시스템 오류 감지 - 크래시나 치명적 문제
    # ----------------------------------------
    critical_found = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
        for kw in critical_error_keywords
    )
    if critical_found:
        result['critical'] = True
        result['penalty_score'] -= 0.7
    
    # ----------------------------------------
    # (4) 접근 제한 감지 - 방화벽, 권한 문제 등
    # ----------------------------------------
    system_block = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
        for kw in system_keywords
    )
    if system_block:
        # 접근 제한은 정상적인 탐색 과정일 수 있으므로 가벼운 패널티
        result['error'] = True
        result['penalty_score'] -= 0.15
    
    # ----------------------------------------
    # (5) 비효율적 탐색 감지 - 정보 증가가 거의 없는 경우
    # ----------------------------------------
    if knowledge_gain < min_info_gain:
        result['inefficient'] = True
        # 정보 부족 정도에 비례한 패널티
        info_deficit = min_info_gain - knowledge_gain
        result['penalty_score'] -= info_deficit * 15  # 계수 조정 (너무 강하지 않게)
    
    # ----------------------------------------
    # (6) 최종 패널티 점수 제한
    # ----------------------------------------
    # 한 번의 행동으로 너무 큰 패널티를 받지 않도록 하한선 설정
    result['penalty_score'] = max(-1.0, result['penalty_score'])
    
    return result
