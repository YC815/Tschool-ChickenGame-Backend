"""
指標服務：分配和管理玩家指標（Round 7 之後使用）

需求：指標要以 Round 1 的配對為單位，同一組配對使用同一個符號，
方便玩家實體配對（兩人拿到同樣符號）。
"""
import random

from sqlalchemy.orm import Session

from models import Player, Indicator, Round, Pair


def assign_indicators(room_id: str, db: Session) -> None:
    """
    為房間內所有玩家分配指標符號（依 Round1 配對，一組一符號）

    邏輯：
    - 先找到 Round 1 的配對列表
    - 依序為每個配對指定同一個符號
    - 符號集輪替使用（🍋 🍎 🍇 🍊），配對數大於符號數則重複循環

    參數：
        room_id: 房間 ID
        db: SQLAlchemy Session

    異常：
        ValueError: 沒有找到 Round 1 或配對
    """
    symbols = [
        "🍋", "🍎", "🍇", "🍊", "🍉", "🍌", "🍒", "🍓",
        "🍍", "🥝", "🥑", "🫐", "🥥", "🍑", "🍐", "🥕",
        "🥔", "🌽", "🍆", "🥦", "🌶️", "🧄", "🧅", "🍞",
        "🧀", "🍗", "🍖", "🍤", "🍣", "🍪", "🍿", "🥨"
    ]

    # 1) 找 Round 1
    round1 = db.query(Round).filter(
        Round.room_id == room_id,
        Round.round_number == 1
    ).first()
    if not round1:
        raise ValueError("Round 1 not found for indicator assignment")

    # 2) 取配對
    pairs = db.query(Pair).filter(Pair.round_id == round1.id).all()
    if not pairs:
        raise ValueError("No pairs found in Round 1 for indicator assignment")

    # 3) 依配對指派同一符號（盡量不重複，超過池大小才會循環）
    random.shuffle(symbols)
    pool = symbols[:]

    for pair in pairs:
        if not pool:
            pool = symbols[:]  # 若配對數 > 符號庫，重新洗牌循環
            random.shuffle(pool)
        symbol = pool.pop()
        for player_id in [pair.player1_id, pair.player2_id]:
            indicator = Indicator(
                room_id=room_id,
                player_id=player_id,
                symbol=symbol
            )
            db.add(indicator)

    db.flush()  # 交由外層 transaction 處理 commit


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
