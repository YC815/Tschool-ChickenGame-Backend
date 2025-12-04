"""
指標服務：分配和管理玩家指標（Round 7 之後使用）

指標用途：
- Round 7-10 時，玩家可以看到對手的指標（而不是真實身份）
- 增加遊戲的匿名性和策略性
"""
import random

from sqlalchemy.orm import Session

from models import Player, Indicator


def assign_indicators(room_id: str, db: Session) -> None:
    """
    為房間內所有玩家分配指標符號

    邏輯：
    - 有 4 種符號：🍋 🍎 🍇 🍊
    - 玩家隨機洗牌後依序分配
    - 如果玩家超過 4 人，符號會重複（例如：2 個 🍋, 2 個 🍎, ...）

    參數：
        room_id: 房間 ID
        db: SQLAlchemy Session

    副作用：
        在資料庫中建立 Indicator 記錄

    範例：
        4 位玩家: 每人一個不同符號
        8 位玩家: 每個符號各 2 人
        6 位玩家: 2 個符號各 2 人，2 個符號各 1 人
    """
    symbols = ["🍋", "🍎", "🍇", "🍊"]

    # 1. 取得房間內所有非 Host 玩家
    players = db.query(Player).filter(
        Player.room_id == room_id,
        Player.is_host == False
    ).all()

    # 2. 隨機洗牌（確保符號分配是隨機的）
    random.shuffle(players)

    # 3. 依序分配符號（輪流使用 4 種符號）
    for i, player in enumerate(players):
        symbol = symbols[i % len(symbols)]
        indicator = Indicator(
            room_id=room_id,
            player_id=player.id,
            symbol=symbol
        )
        db.add(indicator)

    # 4. Flush 但不 commit（讓外層 transaction 處理）
    db.flush()


def get_player_indicator(player_id: str, db: Session) -> str:
    """
    取得玩家的指標符號

    參數：
        player_id: 玩家 ID
        db: SQLAlchemy Session

    返回：
        指標符號（例如：🍋）

    異常：
        ValueError: 如果指標尚未分配

    用途：
        Round 7-10 時，顯示對手的指標而不是真實名稱
    """
    indicator = db.query(Indicator).filter(
        Indicator.player_id == player_id
    ).first()

    if not indicator:
        raise ValueError(f"Indicator not assigned for player {player_id}")

    return indicator.symbol


def indicators_already_assigned(room_id: str, db: Session) -> bool:
    """
    檢查房間內是否已經分配過指標

    用途：
        防止重複分配

    參數：
        room_id: 房間 ID
        db: SQLAlchemy Session

    返回：
        True 如果已分配，False 否則
    """
    count = db.query(Indicator).filter(Indicator.room_id == room_id).count()
    return count > 0
