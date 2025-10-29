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

'''
def run_comprehensive_tests():
    """
    오류 메시지 패턴에 따른 음의 보상 적용을 종합적으로 테스트하는 함수
    """
    
    print("=" * 70)
    print("호기심 보상 시스템 - 종합 테스트")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "테스트 1: 정상 작동 (패널티 없음)",
            "action_log": ["nmap -sV 192.168.1.1", "sqlmap -u http://target"],
            "current_action": "dirb http://target/admin",
            "output_log": "Scanning directory... Found: /admin/login.php, /admin/config.php",
            "knowledge_gain": 0.25,
            "step": 50,
            "expected_penalty": False
        },
        {
            "name": "테스트 2: 일반 오류 (error 키워드)",
            "action_log": ["nmap -p 80 target"],
            "current_action": "nmap -p 443 target",
            "output_log": "Error: Connection timeout occurred",
            "knowledge_gain": 0.01,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 3: 접근 거부 (denied 키워드)",
            "action_log": ["sqlmap --dbs"],
            "current_action": "sqlmap --tables -D admin",
            "output_log": "Access denied for user 'guest'@'localhost'",
            "knowledge_gain": 0.002,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 4: 과도한 반복 (6회 반복)",
            "action_log": ["nikto -h target"] * 6,
            "current_action": "nikto -h target",
            "output_log": "Scan complete. No vulnerabilities found.",
            "knowledge_gain": 0.001,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 5: 심각한 크래시 (segmentation fault)",
            "action_log": ["exploit/buffer_overflow"],
            "current_action": "run payload",
            "output_log": "Segmentation fault (core dumped). Fatal error.",
            "knowledge_gain": 0.0,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 6: 방화벽 차단 (firewall blocked)",
            "action_log": ["nmap -sS target"],
            "current_action": "nmap -sT target",
            "output_log": "Firewall blocked the connection request.",
            "knowledge_gain": 0.003,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 7: 복합 오류 (반복 + 오류 + 정보부족)",
            "action_log": ["hydra -l admin -P pass.txt ssh://target"] * 5,
            "current_action": "hydra -l admin -P pass.txt ssh://target",
            "output_log": "Error: Connection refused. Invalid credentials.",
            "knowledge_gain": 0.0,
            "step": 50,
            "expected_penalty": True
        },
        {
            "name": "테스트 8: 초기 단계 높은 호기심 (step=0)",
            "action_log": [],
            "current_action": "nmap -sV target",
            "output_log": "Starting Nmap scan...",
            "knowledge_gain": 0.5,
            "step": 0,
            "expected_penalty": False
        },
        {
            "name": "테스트 9: 후반 단계 감쇠 확인 (step=1000)",
            "action_log": ["various", "commands", "executed"],
            "current_action": "final scan",
            "output_log": "Scan completed successfully.",
            "knowledge_gain": 0.2,
            "step": 1000,
            "expected_penalty": False
        }
    ]
    
    # 테스트 실행
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"{test['name']}")
        print(f"{'='*70}")
        
        # 조건 판별
        conditions = check_negative_reward_conditions(
            action_log=test['action_log'],
            current_action=test['current_action'],
            output_log=test['output_log'],
            knowledge_gain=test['knowledge_gain']
        )
        
        # 보상 계산
        reward = curiosity_reward_with_penalty(
            is_redundant=conditions['redundant'],
            is_error=conditions['error'],
            is_critical=conditions['critical'],
            step=test['step']
        )
        
        # 결과 출력
        print(f"📊 입력 데이터:")
        print(f"  - Action Log 크기: {len(test['action_log'])} 개")
        print(f"  - Current Action: {test['current_action']}")
        print(f"  - Output Log: {test['output_log'][:60]}...")
        print(f"  - Knowledge Gain: {test['knowledge_gain']}")
        print(f"  - Step: {test['step']}")
        
        print(f"\n🔍 판별 결과:")
        print(f"  - Redundant (반복): {conditions['redundant']}")
        print(f"  - Error (오류): {conditions['error']}")
        print(f"  - Critical (심각): {conditions['critical']}")
        print(f"  - Inefficient (비효율): {conditions['inefficient']}")
        print(f"  - Penalty Score: {conditions['penalty_score']:.4f}")
        
        print(f"\n🎯 최종 보상:")
        print(f"  - Curiosity Reward: {reward:.4f}")
        
        # 검증
        has_penalty = conditions['penalty_score'] < 0
        test_passed = has_penalty == test['expected_penalty']
        
        print(f"\n✅ 테스트 결과: {'통과' if test_passed else '실패'}")
        if not test_passed:
            print(f"   예상: 패널티 {'있음' if test['expected_penalty'] else '없음'}")
            print(f"   실제: 패널티 {'있음' if has_penalty else '없음'}")
    
    print(f"\n{'='*70}")
    print("모든 테스트 완료!")
    print(f"{'='*70}")


# 테스트 실행
run_comprehensive_tests()
'''