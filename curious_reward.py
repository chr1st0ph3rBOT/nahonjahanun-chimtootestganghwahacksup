#뭐가 어떻게 될지 몰라 일단 함수 기틀만 만들어 보았음.
'''우선, 호기심 보상 함수를 두가지 버전으로 만들어보앗는데,
첫번째로는 은세가 말했던 스텝이 진행될 수록 기틀이 잡히니까 호기심 보상을 자동적으로 감쇠시키는 버전,
두번째로는 후반에 가서도 호기심 보상을 감소시키지 않을 수 있게 최악의 상태일떄 음의 보상으로 패치하는 버전으로 만들었음.
'''


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
