import math
import re

# ========================================================
# 호기심 보상 시스템 설정값 (전역 상수)
# ========================================================

# 보상 스케일 설정
CURIOSITY_BASE_REWARD = 1.0          # 호기심 기본 보상
CURIOSITY_MIN_REWARD = -1.0          # 호기심 최소 보상 (음수 제한)
CURIOSITY_MAX_REWARD = 1.0           # 호기심 최대 보상

# 감쇠 설정
DECAY_STRENGTH = 0.1                 # 로그 감쇠 강도

# 패널티 기준
MAX_ALLOWED_REPEATS = 5              # 반복 허용 횟수
MIN_INFO_GAIN_THRESHOLD = 0.005      # 정보 증가 최소 임계값

# 패널티 강도
PENALTY_REDUNDANT = 0.2              # 반복 행동 패널티
PENALTY_ERROR = 0.3                  # 일반 오류 패널티
PENALTY_CRITICAL = 0.7               # 심각한 오류 패널티
PENALTY_ACCESS_DENIED = 0.15         # 접근 제한 패널티
PENALTY_INFO_DEFICIT_MULTIPLIER = 15 # 정보 부족 패널티 배수


# ========================================================
# 1. 자동 감쇠형 호기심 보상 함수 (로그 감쇠)
# ========================================================

def curiosity_reward_decay(step):  # 통합필요: step
    """
    호기심 보상을 로그 함수 형태로 감쇠시키는 함수.
    
    후반부에도 완전히 0이 되지 않고 일정 수준 유지.
    수식: R_c(t) = BASE / (1 + DECAY_STRENGTH * log(1 + step))
    
    Parameters:
    - step: 현재 스텝 수 (전체 학습 진행도)  # 통합필요
    
    Returns:
    - 감쇠된 호기심 보상  # 통합필요
    """
    reward = CURIOSITY_BASE_REWARD / (1 + DECAY_STRENGTH * math.log1p(step))
    
    # 보상 범위 제한
    reward = max(CURIOSITY_MIN_REWARD, min(CURIOSITY_MAX_REWARD, reward))
    
    return reward  # 통합필요


# ========================================================
# 2. 음의 보상 포함형 호기심 보상 함수
# ========================================================

def curiosity_reward_with_penalty(is_redundant, is_error, is_critical, step):  # 통합필요: step
    """
    로그 감쇠 + 조건부 음의 보상을 결합한 호기심 보상 함수.
    
    Parameters:
    - is_redundant: 과도한 반복 여부  # 통합필요
    - is_error: 일반 오류 발생 여부  # 통합필요
    - is_critical: 심각한 시스템 오류 발생 여부  # 통합필요
    - step: 현재 스텝 수  # 통합필요
    
    Returns:
    - 최종 호기심 보상  # 통합필요
    """
    # 기본 로그 감쇠 적용
    reward = CURIOSITY_BASE_REWARD / (1 + DECAY_STRENGTH * math.log1p(step))
    
    # 조건부 패널티 적용
    if is_redundant:
        reward -= PENALTY_REDUNDANT
    if is_error:
        reward -= PENALTY_ERROR
    if is_critical:
        reward -= PENALTY_CRITICAL
    
    # 보상 범위 제한
    reward = max(CURIOSITY_MIN_REWARD, min(CURIOSITY_MAX_REWARD, reward))
    
    return reward  # 통합필요


# ========================================================
# 3. 음의 보상 조건 판별 함수
# ========================================================

def check_negative_reward_conditions(
        action_log,         # 통합필요: 지금까지 수행한 행동 리스트
        current_action,     # 통합필요: 현재 수행한 행동
        output_log,         # 통합필요: 툴 실행 후 출력 로그
        knowledge_gain,     # 통합필요: 이번 행동으로 얻은 정보량 (0~1)
        error_keywords=None,
        critical_error_keywords=None,
        system_keywords=None):
    """
    음의 보상 부여 조건을 감지하는 함수.
    
    Parameters:
    - action_log: 이전까지 수행된 모든 행동 리스트  # 통합필요
    - current_action: 현재 시도한 행동  # 통합필요
    - output_log: 명령 실행 후 출력된 로그 텍스트  # 통합필요
    - knowledge_gain: 이번 행동을 통해 얻은 새로운 정보의 양 (0~1 스케일)  # 통합필요
    
    Returns:
    - dict: {
        'redundant': bool,      # 과도한 반복 여부  # 통합필요
        'error': bool,          # 일반 오류 발생 여부  # 통합필요
        'critical': bool,       # 심각한 오류 여부  # 통합필요
        'inefficient': bool,    # 비효율적 탐색 여부  # 통합필요
        'penalty_score': float  # 총 패널티 점수 (음수)  # 통합필요
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
    
    # 결과 초기화
    result = {
        'redundant': False,      # 통합필요
        'error': False,          # 통합필요
        'critical': False,       # 통합필요
        'inefficient': False,    # 통합필요
        'penalty_score': 0.0     # 통합필요
    }
    
    # (1) 반복 행동 감지
    repeat_count = action_log.count(current_action)  # 통합필요: action_log, current_action
    if repeat_count >= MAX_ALLOWED_REPEATS:
        result['redundant'] = True  # 통합필요
        excess_repeats = repeat_count - MAX_ALLOWED_REPEATS + 1
        result['penalty_score'] -= PENALTY_REDUNDANT * excess_repeats  # 통합필요
    
    # (2) 일반 오류 감지
    error_found = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE)  # 통합필요: output_log
        for kw in error_keywords
    )
    if error_found:
        result['error'] = True  # 통합필요
        result['penalty_score'] -= PENALTY_ERROR  # 통합필요
    
    # (3) 심각한 시스템 오류 감지
    critical_found = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE)  # 통합필요: output_log
        for kw in critical_error_keywords
    )
    if critical_found:
        result['critical'] = True  # 통합필요
        result['penalty_score'] -= PENALTY_CRITICAL  # 통합필요
    
    # (4) 접근 제한 감지
    system_block = any(
        re.search(rf"\b{kw}\b", output_log, re.IGNORECASE)  # 통합필요: output_log
        for kw in system_keywords
    )
    if system_block:
        result['error'] = True  # 통합필요
        result['penalty_score'] -= PENALTY_ACCESS_DENIED  # 통합필요
    
    # (5) 비효율적 탐색 감지
    if knowledge_gain < MIN_INFO_GAIN_THRESHOLD:  # 통합필요: knowledge_gain
        result['inefficient'] = True  # 통합필요
        info_deficit = MIN_INFO_GAIN_THRESHOLD - knowledge_gain
        result['penalty_score'] -= info_deficit * PENALTY_INFO_DEFICIT_MULTIPLIER  # 통합필요
    
    # (6) 패널티 점수 범위 제한
    result['penalty_score'] = max(CURIOSITY_MIN_REWARD, result['penalty_score'])  # 통합필요
    
    return result  # 통합필요
