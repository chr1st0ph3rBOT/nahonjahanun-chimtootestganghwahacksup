#뭐가 어떻게 될지 몰라 일단 함수 기틀만 만들어 보았음.
'''우선, 호기심 보상 함수를 두가지 버전으로 만들어보앗는데,
첫번째로는 은세가 말했던 스텝이 진행될 수록 기틀이 잡히니까 호기심 보상을 자동적으로 감쇠시키는 버전,
두번째로는 후반에 가서도 호기심 보상을 감소시키지 않을 수 있게 최악의 상태일떄 음의 보상으로 패치하는 버전으로 만들었음.
'''
#통합이 필요한 변수명에는 #을 다시달아서 알려주기.

#자동 감쇠형 호기심 함수
def curiosity_reward_decay(step, base_reward=1.0, decay_rate=0.005):
    """
    호기심 보상이 스텝(step)에 따라 자연스럽게 감소하는 함수.
    예: 초반엔 높은 보상, 후반으로 갈수록 점점 감소.

    R_c(t) = base_reward * (1 - decay_rate * step)
    (단, 0보다 작으면 0으로 제한)
    """
    reward = max(base_reward * (1 - decay_rate * step), 0)
    return reward
# 최악의 경우에 음의 보상을 주는 호기심 함수
def curiosity_reward_with_penalty(is_redundant=False, is_error=False, step=0,
                                  base_reward=1.0, penalty_redundant=0.3, penalty_error=0.5,
                                  decay_rate=0.003):
    """
    스텝 수에 따른 호기심 보상 감소 + 잘못된 행동에 대한 음의 보상 적용.

    Parameters:
    - is_redundant: 이미 여러 번 시도된 동일한 행동 수행시 True
    - is_error: 시스템 오류를 유발하는 탐색시 True
    - step: 현재 스텝 수
    - base_reward: 기본 호기심 보상
    - penalty_redundant: 반복 행동에 부여할 음의 보상 강도
    - penalty_error: 심각한 오류 행위에 부여할 음의 보상 강도
    - decay_rate: 스텝에 따른 감쇠 비율
    """
    reward = max(base_reward * (1 - decay_rate * step), 0)
    if is_redundant:
        reward -= penalty_redundant
    if is_error:
        reward -= penalty_error
    return max(reward, -1.0)


'''
import re

def check_negative_reward_conditions(action_log, current_action, output_log, knowledge_gain,
                                     max_repeats=3, min_info_gain=0.01,
                                     error_keywords=None, critical_error_keywords=None,
                                     system_keywords=None):
    """
    음의 보상 조건을 감지하며, 패널티 점수를 음수 값으로 반환한다.
    """

    if error_keywords is None:
        error_keywords = ["error", "failed", "exception", "denied", "invalid"]

    if critical_error_keywords is None:
        critical_error_keywords = ["segmentation fault", "core dumped", "crash", "fatal", "terminated"]

    if system_keywords is None:
        system_keywords = ["unauthorized", "access denied", "permission", "firewall"]

    result = {
        'redundant': False,
        'error': False,
        'critical': False,
        'inefficient': False,
        'penalty_score': 0.0
    }

    # (1) 반복된 행동 감지
    repeat_count = action_log.count(current_action)
    if repeat_count >= max_repeats:
        result['redundant'] = True
        result['penalty_score'] -= 0.3 * (repeat_count - max_repeats + 1)

    # (2) 일반 오류 로그 탐지
    if any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in error_keywords):
        result['error'] = True
        result['penalty_score'] -= 0.5

    # (3) 시스템 크래시나 심각한 오류
    if any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in critical_error_keywords):
        result['critical'] = True
        result['penalty_score'] -= 1.0

    # (4) 접근 제한 관련 단어 감지 (방화벽, 권한 등)
    if any(re.search(rf"\b{kw}\b", output_log, re.IGNORECASE) for kw in system_keywords):
        result['error'] = True
        result['penalty_score'] -= 0.2

    # (5) 새로운 지식이 거의 없는 경우 (비효율)
    if knowledge_gain < min_info_gain:
        result['inefficient'] = True
        result['penalty_score'] -= (min_info_gain - knowledge_gain) * 2

    # (6) 최소값 한정 (과도한 음의 보상 방지)
    result['penalty_score'] = max(-1.0, result['penalty_score'])

    return result
'''
