import hashlib
import hmac
import math
import re

# ========================================================
# 보상 함수 통합 테스트 스크립트
# ========================================================

"""
이 파일은 다음 보상 함수들을 통합적으로 테스트합니다:
1. curiosity_reward_decay() - 로그 감쇠형 호기심 보상
2. curiosity_reward_with_penalty() - 음의 보상 포함형 호기심 보상
3. check_negative_reward_conditions() - 오류 감지 및 패널티 계산
4. flag_reward() - 플래그 정답 보상
"""

# 전역 상수들을 여기서 import한다고 가정
# from reward_functions import *


def run_integrated_reward_tests():
    """
    모든 보상 함수를 통합적으로 테스트하는 메인 함수
    """
    
    print("=" * 80)
    print("통합 보상 시스템 테스트")
    print("=" * 80)
    
    # ========================================
    # 테스트 1: 호기심 보상 감쇠 테스트
    # ========================================
    print("\n[테스트 1] 호기심 보상 감쇠 (curiosity_reward_decay)")
    print("-" * 60)
    
    test_steps = [0, 10, 50, 100, 200, 500, 1000]
    for step in test_steps:
        reward = curiosity_reward_decay(step)
        print(f"Step {step:4d}: Curiosity Reward = {reward:.4f}")
    
    
    # ========================================
    # 테스트 2: 오류 감지 및 패널티 계산 테스트
    # ========================================
    print("\n[테스트 2] 오류 감지 및 패널티 (check_negative_reward_conditions)")
    print("-" * 60)
    
    error_test_cases = [
        {
            "name": "정상 작동",
            "action_log": ["nmap -sV target", "sqlmap --crawl"],
            "current_action": "dirb http://target",
            "output_log": "Scanning completed. Found 3 directories.",
            "knowledge_gain": 0.25
        },
        {
            "name": "일반 오류 발생",
            "action_log": ["nmap -p 80"],
            "current_action": "nmap -p 443",
            "output_log": "Error: Connection timeout occurred",
            "knowledge_gain": 0.01
        },
        {
            "name": "과도한 반복 (6회)",
            "action_log": ["nikto -h target"] * 6,
            "current_action": "nikto -h target",
            "output_log": "Scan complete.",
            "knowledge_gain": 0.001
        },
        {
            "name": "심각한 크래시",
            "action_log": ["exploit/test"],
            "current_action": "buffer overflow",
            "output_log": "Segmentation fault (core dumped)",
            "knowledge_gain": 0.0
        },
        {
            "name": "방화벽 차단",
            "action_log": ["nmap -sS"],
            "current_action": "nmap -sT",
            "output_log": "Firewall blocked the connection",
            "knowledge_gain": 0.003
        }
    ]
    
    for i, test in enumerate(error_test_cases, 1):
        print(f"\n  {i}. {test['name']}")
        conditions = check_negative_reward_conditions(
            action_log=test['action_log'],
            current_action=test['current_action'],
            output_log=test['output_log'],
            knowledge_gain=test['knowledge_gain']
        )
        print(f"     Redundant: {conditions['redundant']}")
        print(f"     Error: {conditions['error']}")
        print(f"     Critical: {conditions['critical']}")
        print(f"     Inefficient: {conditions['inefficient']}")
        print(f"     Penalty Score: {conditions['penalty_score']:.4f}")
    
    
    # ========================================
    # 테스트 3: 음의 보상 포함형 호기심 보상 테스트
    # ========================================
    print("\n[테스트 3] 음의 보상 포함형 호기심 보상 (curiosity_reward_with_penalty)")
    print("-" * 60)
    
    penalty_test_cases = [
        {"redundant": False, "error": False, "critical": False, "step": 50, "name": "정상"},
        {"redundant": True, "error": False, "critical": False, "step": 50, "name": "반복"},
        {"redundant": False, "error": True, "critical": False, "step": 50, "name": "오류"},
        {"redundant": False, "error": False, "critical": True, "step": 50, "name": "심각"},
        {"redundant": True, "error": True, "critical": True, "step": 50, "name": "복합"},
    ]
    
    for i, test in enumerate(penalty_test_cases, 1):
        reward = curiosity_reward_with_penalty(
            is_redundant=test['redundant'],
            is_error=test['error'],
            is_critical=test['critical'],
            step=test['step']
        )
        print(f"  {i}. {test['name']:6s} → Reward: {reward:.4f}")
    
    
    # ========================================
    # 테스트 4: 플래그 보상 테스트
    # ========================================
    print("\n[테스트 4] 플래그 정답 보상 (flag_reward)")
    print("-" * 60)
    
    # 정답 플래그 설정
    correct_flag = "FLAG{test_flag_12345}"
    correct_hash = hashlib.sha256(correct_flag.encode("utf-8")).hexdigest()
    known_flags = {"FLAG": correct_hash}
    
    flag_test_cases = [
        {"flag": correct_flag, "name": "정답 플래그"},
        {"flag": "FLAG{wrong_flag}", "name": "오답 플래그"},
        {"flag": "", "name": "빈 문자열"},
        {"flag": "random_string", "name": "무효한 입력"}
    ]
    
    for i, test in enumerate(flag_test_cases, 1):
        reward = flag_reward(test['flag'], known_flags, big_reward=1000.0)
        print(f"  {i}. {test['name']:15s} → Reward: {reward:.1f}")
    
    
    # ========================================
    # 테스트 5: 통합 시나리오 테스트
    # ========================================
    print("\n[테스트 5] 통합 시나리오 테스트")
    print("-" * 60)
    
    scenarios = [
        {
            "name": "시나리오 A: 정상 탐색 후 플래그 발견",
            "step": 100,
            "action_log": ["scan", "enum", "exploit"],
            "current_action": "check_flag",
            "output_log": "Success: Flag found!",
            "knowledge_gain": 0.8,
            "flag": correct_flag
        },
        {
            "name": "시나리오 B: 반복된 시도 후 오류 발생",
            "step": 150,
            "action_log": ["brute_force"] * 6,
            "current_action": "brute_force",
            "output_log": "Error: Too many requests. Timeout.",
            "knowledge_gain": 0.001,
            "flag": ""
        },
        {
            "name": "시나리오 C: 심각한 오류 발생",
            "step": 200,
            "action_log": ["overflow_test"],
            "current_action": "buffer_exploit",
            "output_log": "Segmentation fault (core dumped)",
            "knowledge_gain": 0.0,
            "flag": ""
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n  {scenario['name']}")
        
        # 오류 조건 확인
        conditions = check_negative_reward_conditions(
            action_log=scenario['action_log'],
            current_action=scenario['current_action'],
            output_log=scenario['output_log'],
            knowledge_gain=scenario['knowledge_gain']
        )
        
        # 호기심 보상 계산
        curiosity = curiosity_reward_with_penalty(
            is_redundant=conditions['redundant'],
            is_error=conditions['error'],
            is_critical=conditions['critical'],
            step=scenario['step']
        )
        
        # 플래그 보상 계산
        flag_bonus = flag_reward(scenario['flag'], known_flags, big_reward=1000.0)
        
        # 총 보상
        total_reward = curiosity + flag_bonus
        
        print(f"     Curiosity Reward: {curiosity:8.4f}")
        print(f"     Flag Bonus:       {flag_bonus:8.1f}")
        print(f"     Total Reward:     {total_reward:8.4f}")
        print(f"     Penalty Score:    {conditions['penalty_score']:.4f}")
    
    
    # ========================================
    # 테스트 6: 엣지 케이스 테스트
    # ========================================
    print("\n[테스트 6] 엣지 케이스 테스트")
    print("-" * 60)
    
    print("\n  1. Step = 0 (초기 단계)")
    r1 = curiosity_reward_decay(0)
    print(f"     Curiosity Reward: {r1:.4f}")
    
    print("\n  2. Step = 10000 (매우 후반)")
    r2 = curiosity_reward_decay(10000)
    print(f"     Curiosity Reward: {r2:.4f}")
    
    print("\n  3. 모든 패널티 동시 적용")
    r3 = curiosity_reward_with_penalty(
        is_redundant=True,
        is_error=True,
        is_critical=True,
        step=100
    )
    print(f"     Final Reward: {r3:.4f}")
    
    print("\n  4. 빈 action_log")
    conditions = check_negative_reward_conditions(
        action_log=[],
        current_action="first_action",
        output_log="Starting...",
        knowledge_gain=0.5
    )
    print(f"     Penalty Score: {conditions['penalty_score']:.4f}")
    
    print("\n  5. 매우 높은 knowledge_gain")
    conditions = check_negative_reward_conditions(
        action_log=["action"],
        current_action="action",
        output_log="Success!",
        knowledge_gain=1.0
    )
    print(f"     Penalty Score: {conditions['penalty_score']:.4f}")
    
    
    # ========================================
    # 테스트 완료
    # ========================================
    print("\n" + "=" * 80)
    print("모든 테스트 완료!")
    print("=" * 80)


# ========================================================
# 함수 정의 (테스트용 - 실제로는 import로 대체)
# ========================================================

# 전역 상수
CURIOSITY_BASE_REWARD = 1.0
CURIOSITY_MIN_REWARD = -1.0
CURIOSITY_MAX_REWARD = 1.0
DECAY_STRENGTH = 0.1
MAX_ALLOWED_REPEATS = 5
MIN_INFO_GAIN_THRESHOLD = 0.005
PENALTY_REDUNDANT = 0.2
PENALTY_ERROR = 0.3
PENALTY_CRITICAL = 0.7
PENALTY_ACCESS_DENIED = 0.15
PENALTY_INFO_DEFICIT_MULTIPLIER = 15


def curiosity_reward_decay(step):
    reward = CURIOSITY_BASE_REWARD / (1 + DECAY_STRENGTH * math.log1p(step))
    reward = max(CURIOSITY_MIN_REWARD, min(CURIOSITY_MAX_REWARD, reward))
    return reward


def curiosity_reward_with_penalty(is_redundant, is_error, is_critical, step):
    reward = CURIOSITY_BASE_REWARD / (1 + DECAY_STRENGTH * math.log1p(step))
    if is_redundant:
        reward -= PENALTY_REDUNDANT
    if is_error:
        reward -= PENALTY_ERROR
    if is_critical:
        reward -= PENALTY_CRITICAL
    reward = max(CURIOSITY_MIN_REWARD, min(CURIOSITY_MAX_REWARD, reward))
    return reward


def check_negative_reward_conditions(action_log, current_action, output_log, knowledge_gain,
                                     error_keywords=None, critical_error_keywords=None,
                                     system_keywords=None):
    if error_keywords is None:
        error_keywords = ["error", "failed", "exception", "denied", "invalid", "timeout", "refused", "not found"]
    if critical_error_keywords is None:
        critical_error_keywords = ["segmentation fault", "core dumped", "crash", "fatal", "terminated", "killed", "panic"]
    if system_keywords is None:
        system_keywords = ["unauthorized", "access denied", "permission", "firewall", "blocked", "forbidden"]
    
    result = {
        'redundant': False,
        'error': False,
        'critical': False,
        'inefficient': False,
        'penalty_score': 0.0
    }
    
    repeat_count = action_log.count(current_action)
    if repeat_count >= MAX_ALLOWED_REPEATS:
        result['redundant'] = True
        excess_repeats = repeat_count - MAX_ALLOWED_REPEATS + 1
        result['penalty_score'] -= PENALTY_REDUNDANT * excess_repeats
    
    error_found = any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in error_keywords)
    if error_found:
        result['error'] = True
        result['penalty_score'] -= PENALTY_ERROR
    
    critical_found = any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in critical_error_keywords)
    if critical_found:
        result['critical'] = True
        result['penalty_score'] -= PENALTY_CRITICAL
    
    system_block = any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in system_keywords)
    if system_block:
        result['error'] = True
        result['penalty_score'] -= PENALTY_ACCESS_DENIED
    
    if knowledge_gain < MIN_INFO_GAIN_THRESHOLD:
        result['inefficient'] = True
        info_deficit = MIN_INFO_GAIN_THRESHOLD - knowledge_gain
        result['penalty_score'] -= info_deficit * PENALTY_INFO_DEFICIT_MULTIPLIER
    
    result['penalty_score'] = max(CURIOSITY_MIN_REWARD, result['penalty_score'])
    return result


def flag_reward(flag_str, known_flags, big_reward=1000.0):
    if not isinstance(flag_str, str):
        return 0.0
    submitted_hash = hashlib.sha256(flag_str.strip().encode("utf-8")).hexdigest()
    try:
        expected_key, expected_hash = next(iter(known_flags.items()))
    except StopIteration:
        return 0.0
    is_correct = hmac.compare_digest(submitted_hash, expected_hash)
    reward = float(big_reward) if is_correct else 0.0
    return reward


# ========================================================
# 실행
# ========================================================

if __name__ == "__main__":