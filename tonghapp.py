import hashlib
import hmac
import math
import re

# ========================================================
# tanh 기반 정규화 보상 시스템 (일관성 보장)
# ========================================================

"""
모든 보상을 tanh 함수로 정규화하여 -1.0 ~ +1.0 범위로 제한.
치명도에 따라 일관성 있는 보상 체계 제공.

보상 범위:
- 극단적 양수: +1.0 (플래그 정답)
- 중간 양수: +0.3 ~ +0.7 (정상 탐색, 정보 획득)
- 중립: 0.0 (보통 행동)
- 중간 음수: -0.3 ~ -0.7 (일반 오류, 비효율)
- 극단적 음수: -1.0 (심각한 크래시, 시스템 파괴)
"""

# ========================================================
# 전역 상수
# ========================================================

# 보상 스케일 (tanh 입력값)
CURIOSITY_BASE_SCALE = 1.5           # 호기심 기본 스케일
DECAY_STRENGTH = 0.1                 # 로그 감쇠 강도

# 패널티 기준
MAX_ALLOWED_REPEATS = 5              # 반복 허용 횟수
MIN_INFO_GAIN_THRESHOLD = 0.005      # 정보 증가 최소 임계값

# 치명도 레벨 (tanh 입력값)
SEVERITY_REDUNDANT = -0.8            # 반복 행동 치명도
SEVERITY_MINOR_ERROR = -1.2          # 경미한 오류 (접근 거부 등)
SEVERITY_MODERATE_ERROR = -2.0       # 중간 오류 (일반 에러)
SEVERITY_SEVERE_ERROR = -3.0         # 심각한 오류 (크래시, 세그폴트)
SEVERITY_INFO_DEFICIT = -1.5         # 정보 부족 치명도

# 플래그 보상 스케일
FLAG_REWARD_SCALE = 5.0              # 플래그 정답 시 tanh 입력값 (→ ~1.0)


# ========================================================
# 핵심 함수: tanh 정규화
# ========================================================

def normalize_reward(raw_score):
    """
    raw_score를 tanh로 정규화하여 -1.0 ~ +1.0 범위로 변환
    
    Parameters:
    - raw_score: 원시 점수 (음수/양수 모두 가능)
    
    Returns:
    - normalized_reward: -1.0 ~ +1.0 사이의 정규화된 보상  # 통합필요
    """
    return math.tanh(raw_score)  # 통합필요


# ========================================================
# 1. 호기심 보상 함수 (tanh 정규화)
# ========================================================

def curiosity_reward_normalized(step, knowledge_gain):  # 통합필요: step, knowledge_gain
    """
    로그 감쇠 + 정보 획득량을 고려한 정규화 호기심 보상.
    
    Parameters:
    - step: 현재 스텝 수  # 통합필요
    - knowledge_gain: 이번 행동으로 얻은 정보량 (0~1)  # 통합필요
    
    Returns:
    - normalized_reward: -1.0 ~ +1.0 사이의 호기심 보상  # 통합필요
    """
    # 로그 감쇠 적용 (초반 높음, 후반 낮음)
    decay_factor = 1.0 / (1 + DECAY_STRENGTH * math.log1p(step))
    
    # 정보 획득량 기반 원시 점수
    raw_score = CURIOSITY_BASE_SCALE * decay_factor * knowledge_gain
    
    # tanh 정규화
    return normalize_reward(raw_score)  # 통합필요


# ========================================================
# 2. 오류 감지 및 치명도 기반 패널티 계산
# ========================================================

def detect_errors_and_calculate_severity(
        action_log,         # 통합필요: 지금까지 수행한 행동 리스트
        current_action,     # 통합필요: 현재 수행한 행동
        output_log,         # 통합필요: 툴 실행 후 출력 로그
        knowledge_gain):    # 통합필요: 이번 행동으로 얻은 정보량 (0~1)
    """
    오류를 감지하고 치명도를 계산하여 정규화된 패널티를 반환.
    
    Returns:
    - dict: {
        'redundant': bool,              # 반복 감지  # 통합필요
        'error_type': str,              # 오류 유형  # 통합필요
        'severity_score': float,        # 원시 치명도 점수 (음수)  # 통합필요
        'normalized_penalty': float     # 정규화된 패널티 (-1~0)  # 통합필요
      }
    """
    
    result = {
        'redundant': False,              # 통합필요
        'error_type': 'none',            # 통합필요
        'severity_score': 0.0,           # 통합필요
        'normalized_penalty': 0.0        # 통합필요
    }
    
    # (1) 반복 행동 감지
    repeat_count = action_log.count(current_action)
    if repeat_count >= MAX_ALLOWED_REPEATS:
        result['redundant'] = True
        result['error_type'] = 'redundant'
        excess = (repeat_count - MAX_ALLOWED_REPEATS + 1)
        result['severity_score'] += SEVERITY_REDUNDANT * excess
    
    # (2) 심각한 크래시 감지 (최우선)
    critical_keywords = ["segmentation fault", "core dumped", "crash", "fatal", "panic", "killed"]
    if any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in critical_keywords):
        result['error_type'] = 'critical'
        result['severity_score'] += SEVERITY_SEVERE_ERROR
    
    # (3) 중간 오류 감지
    elif any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
             for kw in ["error", "failed", "exception", "timeout"]):
        result['error_type'] = 'moderate'
        result['severity_score'] += SEVERITY_MODERATE_ERROR
    
    # (4) 경미한 오류 (접근 제한)
    elif any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
             for kw in ["access denied", "permission denied", "unauthorized", "firewall", "blocked"]):
        result['error_type'] = 'minor'
        result['severity_score'] += SEVERITY_MINOR_ERROR
    
    # (5) 정보 부족
    if knowledge_gain < MIN_INFO_GAIN_THRESHOLD:
        info_deficit = (MIN_INFO_GAIN_THRESHOLD - knowledge_gain) * 100
        result['severity_score'] += SEVERITY_INFO_DEFICIT * info_deficit
    
    # (6) tanh 정규화
    result['normalized_penalty'] = normalize_reward(result['severity_score'])
    
    return result  # 통합필요


# ========================================================
# 3. 통합 호기심 보상 (패널티 포함)
# ========================================================

def integrated_curiosity_reward(
        action_log,         # 통합필요
        current_action,     # 통합필요
        output_log,         # 통합필요
        knowledge_gain,     # 통합필요
        step):              # 통합필요
    """
    호기심 보상 + 오류 패널티를 통합하여 최종 정규화 보상 반환.
    
    Returns:
    - dict: {
        'curiosity_reward': float,      # 순수 호기심 보상  # 통합필요
        'penalty': float,               # 오류 패널티  # 통합필요
        'total_reward': float,          # 최종 보상 (-1~+1)  # 통합필요
        'error_type': str               # 감지된 오류 유형  # 통합필요
      }
    """
    
    # 순수 호기심 보상
    curiosity = curiosity_reward_normalized(step, knowledge_gain)
    
    # 오류 감지 및 패널티
    error_result = detect_errors_and_calculate_severity(
        action_log, current_action, output_log, knowledge_gain
    )
    
    # 최종 보상 = 호기심 + 패널티
    total = curiosity + error_result['normalized_penalty']
    
    # -1.0 ~ +1.0 범위로 클리핑
    total = max(-1.0, min(1.0, total))
    
    return {
        'curiosity_reward': curiosity,                      # 통합필요
        'penalty': error_result['normalized_penalty'],     # 통합필요
        'total_reward': total,                             # 통합필요
        'error_type': error_result['error_type']           # 통합필요
    }  # 통합필요


# ========================================================
# 4. 플래그 보상 (tanh 정규화)
# ========================================================

def flag_reward_normalized(flag_str, known_flags):  # 통합필요: flag_str, known_flags
    """
    플래그 정답 여부에 따른 정규화 보상.
    
    Parameters:
    - flag_str: 제출된 플래그 문자열  # 통합필요
    - known_flags: {"FLAG": "<sha256_hex>"} 형태의 정답 해시  # 통합필요
    
    Returns:
    - normalized_reward: 정답 시 ~1.0, 오답 시 0.0  # 통합필요
    """
    
    # 입력 검증
    if not isinstance(flag_str, str) or not flag_str.strip():
        return 0.0
    
    # 제출 플래그 해시 계산
    submitted_hash = hashlib.sha256(flag_str.strip().encode("utf-8")).hexdigest()
    
    # 정답 해시 확인
    try:
        expected_key, expected_hash = next(iter(known_flags.items()))
    except StopIteration:
        return 0.0
    
    # 안전 비교
    is_correct = hmac.compare_digest(submitted_hash, expected_hash)
    
    # tanh 정규화 (정답 시 ~1.0)
    raw_score = FLAG_REWARD_SCALE if is_correct else 0.0
    return normalize_reward(raw_score)  # 통합필요


# ========================================================
# 5. 최종 통합 보상 계산
# ========================================================

def calculate_total_reward(
        action_log,         # 통합필요
        current_action,     # 통합필요
        output_log,         # 통합필요
        knowledge_gain,     # 통합필요
        step,               # 통합필요
        flag_str=None,      # 통합필요
        known_flags=None):  # 통합필요
    """
    모든 보상 요소를 통합하여 최종 정규화 보상 반환.
    
    Returns:
    - dict: {
        'curiosity': float,         # 호기심 보상  # 통합필요
        'penalty': float,           # 오류 패널티  # 통합필요
        'flag_bonus': float,        # 플래그 보상  # 통합필요
        'total_reward': float,      # 최종 총 보상  # 통합필요
        'error_type': str           # 오류 유형  # 통합필요
      }
    """
    
    # 호기심 + 패널티
    curiosity_result = integrated_curiosity_reward(
        action_log, current_action, output_log, knowledge_gain, step
    )
    
    # 플래그 보상
    flag_bonus = 0.0
    if flag_str and known_flags:
        flag_bonus = flag_reward_normalized(flag_str, known_flags)
    
    # 최종 보상 = 호기심 + 플래그 보너스
    total = curiosity_result['total_reward'] + flag_bonus
    
    # -1.0 ~ +1.0 범위로 클리핑
    total = max(-1.0, min(1.0, total))
    
    return {
        'curiosity': curiosity_result['curiosity_reward'],  # 통합필요
        'penalty': curiosity_result['penalty'],             # 통합필요
        'flag_bonus': flag_bonus,                           # 통합필요
        'total_reward': total,                              # 통합필요
        'error_type': curiosity_result['error_type']        # 통합필요
    }  # 통합필요


# ========================================================
# 6. 치명도 레벨 시각화 (디버깅용)
# ========================================================

def visualize_severity_levels():
    """
    각 치명도 레벨의 정규화 결과를 시각화
    """
    print("=" * 60)
    print("치명도 레벨별 정규화 보상")
    print("=" * 60)
    
    levels = {
        "반복 행동": SEVERITY_REDUNDANT,
        "경미한 오류 (접근 거부)": SEVERITY_MINOR_ERROR,
        "중간 오류 (일반 에러)": SEVERITY_MODERATE_ERROR,
        "심각한 오류 (크래시)": SEVERITY_SEVERE_ERROR,
        "정보 부족 (1회분)": SEVERITY_INFO_DEFICIT,
        "플래그 정답": FLAG_REWARD_SCALE
    }
    
    for name, raw_score in levels.items():
        normalized = normalize_reward(raw_score)
        print(f"{name:25s}: {raw_score:6.2f} → {normalized:+6.3f}")
    
    print("=" * 60)

    # ========================================================
# 간단한 테스트 코드 (핵심만)
# ========================================================

# 전역 상수
CURIOSITY_BASE_SCALE = 1.5
DECAY_STRENGTH = 0.1
MAX_ALLOWED_REPEATS = 5
MIN_INFO_GAIN_THRESHOLD = 0.005

SEVERITY_REDUNDANT = -0.8
SEVERITY_MINOR_ERROR = -1.2
SEVERITY_MODERATE_ERROR = -2.0
SEVERITY_SEVERE_ERROR = -3.0
SEVERITY_INFO_DEFICIT = -1.5
FLAG_REWARD_SCALE = 5.0


def normalize_reward(raw_score):
    return math.tanh(raw_score)


def curiosity_reward_normalized(step, knowledge_gain):
    decay_factor = 1.0 / (1 + DECAY_STRENGTH * math.log1p(step))
    raw_score = CURIOSITY_BASE_SCALE * decay_factor * knowledge_gain
    return normalize_reward(raw_score)


def detect_errors_and_calculate_severity(action_log, current_action, output_log, knowledge_gain):
    result = {
        'error_type': 'none',
        'severity_score': 0.0,
        'normalized_penalty': 0.0
    }
    
    # 반복 감지
    repeat_count = action_log.count(current_action)
    if repeat_count >= MAX_ALLOWED_REPEATS:
        result['error_type'] = 'redundant'
        excess = (repeat_count - MAX_ALLOWED_REPEATS + 1)
        result['severity_score'] += SEVERITY_REDUNDANT * excess
    
    # 심각한 크래시
    if any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
           for kw in ["segmentation fault", "core dumped", "crash", "fatal", "panic"]):
        result['error_type'] = 'critical'
        result['severity_score'] += SEVERITY_SEVERE_ERROR
    
    # 중간 오류
    elif any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
             for kw in ["error", "failed", "exception", "timeout"]):
        result['error_type'] = 'moderate'
        result['severity_score'] += SEVERITY_MODERATE_ERROR
    
    # 경미한 오류
    elif any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) 
             for kw in ["access denied", "permission denied", "firewall", "blocked"]):
        result['error_type'] = 'minor'
        result['severity_score'] += SEVERITY_MINOR_ERROR
    
    # 정보 부족
    if knowledge_gain < MIN_INFO_GAIN_THRESHOLD:
        info_deficit = (MIN_INFO_GAIN_THRESHOLD - knowledge_gain) * 100
        result['severity_score'] += SEVERITY_INFO_DEFICIT * info_deficit
    
    result['normalized_penalty'] = normalize_reward(result['severity_score'])
    return result


def calculate_total_reward(action_log, current_action, output_log, knowledge_gain, step, 
                          flag_str=None, known_flags=None):
    # 호기심 보상
    curiosity = curiosity_reward_normalized(step, knowledge_gain)
    
    # 오류 패널티
    error_result = detect_errors_and_calculate_severity(
        action_log, current_action, output_log, knowledge_gain
    )
    
    # 플래그 보상
    flag_bonus = 0.0
    if flag_str and known_flags:
        submitted_hash = hashlib.sha256(flag_str.strip().encode("utf-8")).hexdigest()
        try:
            expected_key, expected_hash = next(iter(known_flags.items()))
            if hmac.compare_digest(submitted_hash, expected_hash):
                flag_bonus = normalize_reward(FLAG_REWARD_SCALE)
        except:
            pass
    
    # 최종 보상
    total = curiosity + error_result['normalized_penalty'] + flag_bonus
    total = max(-1.0, min(1.0, total))
    
    return {
        'curiosity': curiosity,
        'penalty': error_result['normalized_penalty'],
        'flag_bonus': flag_bonus,
        'total_reward': total,
        'error_type': error_result['error_type']
    }


# ========================================================
# 간단 테스트 실행
# ========================================================

print("=" * 70)
print("tanh 정규화 보상 시스템 - 간단 테스트")
print("=" * 70)

# 테스트 케이스
test_cases = [
    {
        "name": "1. 정상 탐색 (정보 획득 높음)",
        "action_log": ["scan", "enum"],
        "current_action": "exploit",
        "output_log": "Success! Found vulnerability.",
        "knowledge_gain": 0.8,
        "step": 50
    },
    {
        "name": "2. 일반 오류 발생",
        "action_log": ["test"],
        "current_action": "attack",
        "output_log": "Error: Connection timeout",
        "knowledge_gain": 0.01,
        "step": 50
    },
    {
        "name": "3. 과도한 반복 (6회)",
        "action_log": ["brute"] * 6,
        "current_action": "brute",
        "output_log": "Trying password...",
        "knowledge_gain": 0.001,
        "step": 50
    },
    {
        "name": "4. 심각한 크래시",
        "action_log": ["overflow"],
        "current_action": "exploit",
        "output_log": "Segmentation fault (core dumped)",
        "knowledge_gain": 0.0,
        "step": 50
    },
    {
        "name": "5. 플래그 발견!",
        "action_log": ["scan", "exploit"],
        "current_action": "read_flag",
        "output_log": "Flag found!",
        "knowledge_gain": 1.0,
        "step": 100,
        "flag": "FLAG{test123}"
    }
]

# 플래그 정답 설정
correct_flag = "FLAG{test123}"
correct_hash = hashlib.sha256(correct_flag.encode("utf-8")).hexdigest()
known_flags = {"FLAG": correct_hash}

for i, test in enumerate(test_cases, 1):
    print(f"\n{test['name']}")
    print("-" * 70)
    
    result = calculate_total_reward(
        action_log=test['action_log'],
        current_action=test['current_action'],
        output_log=test['output_log'],
        knowledge_gain=test['knowledge_gain'],
        step=test['step'],
        flag_str=test.get('flag'),
        known_flags=known_flags if test.get('flag') else None
    )
    
    print(f"  호기심 보상:  {result['curiosity']:+.3f}")
    print(f"  패널티:       {result['penalty']:+.3f}")
    print(f"  플래그 보너스:{result['flag_bonus']:+.3f}")
    print(f"  총 보상:      {result['total_reward']:+.3f}")
    print(f"  오류 유형:    {result['error_type']}")

# 치명도 레벨 시각화
print("\n" + "=" * 70)
print("치명도 레벨별 정규화 결과")
print("=" * 70)

levels = {
    "반복 행동": SEVERITY_REDUNDANT,
    "경미한 오류 (접근 거부)": SEVERITY_MINOR_ERROR,
    "중간 오류 (일반 에러)": SEVERITY_MODERATE_ERROR,
    "심각한 오류 (크래시)": SEVERITY_SEVERE_ERROR,
    "플래그 정답": FLAG_REWARD_SCALE
}

for name, raw_score in levels.items():
    normalized = normalize_reward(raw_score)
    print(f"{name:25s}: {raw_score:6.2f} → {normalized:+6.3f}")

print("=" * 70)

def test_normalize_reward():
    import math
    test_scores = [-5, -2, -1, 0, 1, 2, 5]
    print("원시 점수 → tanh 정규화 결과")
    for score in test_scores:
        norm = math.tanh(score)
        print(f"{score:>6} → {norm:.3f}")

# 호기심 보상 및 오류 패널티 간단 테스트
def test_reward_system():
    # 여러 원시 점수 테스트
    raw_scores = [5.0, 1.5, 0.0, -0.8, -2.0, -3.0]
    for score in raw_scores:
        print(f"원시 점수: {score}")
        print(f"정규화 보상: {math.tanh(score):.3f}")

    # 오류 감지 및 보상
    test_cases = [
        # 정상 플래그
        {"flag": "FLAG{correct}", "knowledge_gain": 0.8},
        # 틀린 플래그
        {"flag": "FLAG{wrong}", "knowledge_gain": 0.2},
        # 크래시 오류 메시지
        {"flag": "", "knowledge_gain": 0.1},
        # 정상 행동
        {"flag": "", "knowledge_gain": 0.9}
    ]

    from curiosity_reward import (
        curiosity_reward_normalized,
        detect_errors_and_calculate_severity,
        calculate_total_reward
    )

    for case in test_cases:
        # 오류 감지
        error_result = detect_errors_and_calculate_severity(
            action_log=["test"], current_action="test",
            output_log="Segmentation fault (core dumped)" if not case["flag"] else "All good",
            knowledge_gain=case["knowledge_gain"]
        )

        # 호기심 보상
        reward = curiosity_reward_normalized(100, case["knowledge_gain"])
        # 총 통합 보상 (가볍게 출력)
        total = calculate_total_reward({
            'action_log': ["test"],
            'current_action': "test",
            'output_log': "Segmentation fault (core dumped)" if not case["flag"] else "All good",
            'knowledge_gain': case["knowledge_gain"]
        })

        print(f"\n플래그: {case['flag']}")
        print(f"오류 감지: {error_result}")
        print(f"호기심 보상 (정규화): {reward:.3f}")
        print(f"총 보상: {total:.3f}")

# 단순 테스트 호출
if __name__ == "__main__":
    test_normalize_reward()
    print("\n" + "="*40 + "\n")
    test_reward_system()
