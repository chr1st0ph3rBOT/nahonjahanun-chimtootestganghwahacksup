import hashlib
import hmac
import math
import re

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