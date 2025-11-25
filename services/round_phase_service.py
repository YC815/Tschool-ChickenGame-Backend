"""
回合階段服務：判斷回合的特殊階段

Chicken Game 的回合設計：
- Round 1-4, 7-10: NORMAL（正常遊戲）
- Round 5-6: MESSAGE（可以發送訊息給對手）
- Round 7: INDICATOR（分配指標後，開始用指標辨識對手）
"""
from models import RoundPhase


def get_round_phase(round_number: int) -> RoundPhase:
    """
    根據回合數決定回合階段

    規則：
    - Round 5-6: MESSAGE 階段（玩家可以互相發訊息）
    - Round 7: INDICATOR 階段（分配指標，之後用指標辨識對手）
    - 其他: NORMAL 階段（正常遊戲）

    參數：
        round_number: 回合數（1-10）

    返回：
        RoundPhase enum

    範例：
        get_round_phase(3) -> RoundPhase.NORMAL
        get_round_phase(5) -> RoundPhase.MESSAGE
        get_round_phase(7) -> RoundPhase.INDICATOR
        get_round_phase(9) -> RoundPhase.NORMAL
    """
    if round_number in [5, 6]:
        return RoundPhase.MESSAGE
    elif round_number == 7:
        return RoundPhase.INDICATOR
    else:
        return RoundPhase.NORMAL


def is_message_round(round_number: int) -> bool:
    """
    檢查是否為訊息回合

    用途：
        API 層判斷是否允許發送訊息

    參數：
        round_number: 回合數

    返回：
        True 如果是 Round 5 或 6，False 否則
    """
    return round_number in [5, 6]


def should_assign_indicators(round_number: int) -> bool:
    """
    檢查是否應該在此回合分配指標

    用途：
        判斷是否該呼叫 IndicatorService.assign_indicators()

    參數：
        round_number: 回合數

    返回：
        True 如果是 Round 7，False 否則
    """
    return round_number == 7
