"""
自定義異常類別

集中管理所有業務邏輯異常，方便 API 層統一處理
"""


class ChickenGameException(Exception):
    """所有遊戲異常的基類"""
    pass


# ============ Room 相關異常 ============

class RoomNotFound(ChickenGameException):
    """房間不存在"""
    def __init__(self, room_id):
        self.room_id = room_id
        super().__init__(f"Room {room_id} not found")


class InvalidPlayerCount(ChickenGameException):
    """玩家數量不符合要求（必須是偶數且 >= 2）"""
    pass


class RoomNotAcceptingPlayers(ChickenGameException):
    """房間不接受新玩家加入（已經開始遊戲）"""
    pass


# ============ Round 相關異常 ============

class RoundNotFound(ChickenGameException):
    """回合不存在"""
    def __init__(self, round_id):
        self.round_id = round_id
        super().__init__(f"Round {round_id} not found")


class MaxRoundsReached(ChickenGameException):
    """已達最大回合數（10 回合）"""
    pass


class ActionAlreadySubmitted(ChickenGameException):
    """玩家已經提交過動作了"""
    pass


# ============ 狀態轉換異常 ============

class InvalidStateTransition(ChickenGameException):
    """非法的狀態轉換"""
    pass


# ============ Player 相關異常 ============

class PlayerNotFound(ChickenGameException):
    """玩家不存在"""
    def __init__(self, player_id):
        self.player_id = player_id
        super().__init__(f"Player {player_id} not found")


class PairNotFound(ChickenGameException):
    """找不到配對"""
    pass


# ============ Message 相關異常 ============

class MessageNotAllowedInThisRound(ChickenGameException):
    """此回合不允許發送訊息（只有 Round 5-6 可以）"""
    pass


class MessageAlreadySent(ChickenGameException):
    """已經發送過訊息了"""
    pass


# ============ Indicator 相關異常 ============

class IndicatorNotAssignedYet(ChickenGameException):
    """指標尚未分配"""
    pass


class IndicatorsAlreadyAssigned(ChickenGameException):
    """指標已經分配過了"""
    pass
