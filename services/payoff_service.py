"""
計分服務：Chicken Game 的 Payoff 計算邏輯

純計算邏輯，實現 Game Theory 的 Payoff Matrix
"""
from uuid import UUID
from sqlalchemy.orm import Session
from typing import Tuple

from models import Action, Choice, Pair


def calculate_payoff(choice1: Choice, choice2: Choice) -> Tuple[int, int]:
    """
    計算兩個玩家的 Payoff（基於 Game Theory 的 Payoff Matrix）

    Chicken Game Payoff Matrix:
    ┌─────────────────┬────────────┬────────────────┐
    │                 │ P2: Turn   │ P2: Accelerate │
    ├─────────────────┼────────────┼────────────────┤
    │ P1: Turn        │  (3, 3)    │  (-3, 10)      │
    │ P1: Accelerate  │  (10, -3)  │  (-10, -10)    │
    └─────────────────┴────────────┴────────────────┘

    解釋：
    - Turn + Turn: 雙方都讓步 → 小贏 (3, 3)
    - Turn + Accelerate: 一方讓步一方加速 → 讓步者大輸，加速者大贏 (-3, 10)
    - Accelerate + Turn: 同上，反過來 (10, -3)
    - Accelerate + Accelerate: 雙方都不讓步 → 雙輸 (-10, -10)

    這就是 Chicken Game 的核心矛盾：
    - 如果對方會讓步，我應該加速（獲得 10）
    - 但如果對方也加速，雙方都慘輸（-10）
    - 所以雙方都在猜測對方的選擇

    參數：
        choice1: 玩家 1 的選擇
        choice2: 玩家 2 的選擇

    返回：
        (payoff1, payoff2) - 兩個玩家的 Payoff
    """
    if choice1 == Choice.TURN and choice2 == Choice.TURN:
        return (3, 3)
    elif choice1 == Choice.TURN and choice2 == Choice.ACCELERATE:
        return (-3, 10)
    elif choice1 == Choice.ACCELERATE and choice2 == Choice.TURN:
        return (10, -3)
    else:  # both accelerate
        return (-10, -10)


def calculate_round_payoffs(round_id: UUID, db: Session) -> None:
    """
    計算一個回合內所有配對的 Payoff

    流程：
    1. 找出回合內所有配對（Pairs）
    2. 對於每個配對，找出兩個玩家的 Action
    3. 計算 Payoff
    4. 更新 Action 的 payoff 欄位

    注意：
    - 如果有玩家沒提交 Action，該配對會被跳過（不計算）
    - 不改變 Round 的狀態（由 RoundManager 負責）

    參數：
        round_id: 回合 ID
        db: SQLAlchemy Session

    副作用：
        更新 Action.payoff 欄位
    """
    # 1. 找出回合內所有配對
    pairs = db.query(Pair).filter(Pair.round_id == round_id).all()

    # 2. 對於每個配對，計算 Payoff
    for pair in pairs:
        # 2.1 找出玩家 1 的 Action
        action1 = db.query(Action).filter(
            Action.round_id == round_id,
            Action.player_id == pair.player1_id
        ).first()

        # 2.2 找出玩家 2 的 Action
        action2 = db.query(Action).filter(
            Action.round_id == round_id,
            Action.player_id == pair.player2_id
        ).first()

        # 2.3 如果有任一玩家沒提交，跳過此配對
        if not action1 or not action2:
            continue

        # 2.4 計算 Payoff
        payoff1, payoff2 = calculate_payoff(action1.choice, action2.choice)

        # 2.5 更新 Action
        action1.payoff = payoff1
        action2.payoff = payoff2

    # 3. Flush 但不 commit（讓外層 transaction 處理）
    db.flush()


def calculate_total_payoff(player_id: UUID, db: Session) -> int:
    """
    計算一個玩家在整場遊戲的總 Payoff

    用途：
    - 遊戲結束時計算排名
    - 顯示玩家的最終得分

    參數：
        player_id: 玩家 ID
        db: SQLAlchemy Session

    返回：
        總 Payoff（所有回合加總）

    範例：
        Round 1: +3
        Round 2: -10
        Round 3: +10
        Total: 3
    """
    actions = db.query(Action).filter(Action.player_id == player_id).all()
    return sum(action.payoff for action in actions if action.payoff is not None)


def all_actions_submitted(round_id: UUID, db: Session) -> bool:
    """
    檢查一個回合是否所有玩家都已提交 Action

    用途：
    - RoundManager 用來判斷是否可以開始計算結果

    邏輯：
    - 計算房間內非 Host 玩家數量
    - 計算此回合的 Action 數量
    - 如果相等，表示所有人都提交了

    參數：
        round_id: 回合 ID
        db: SQLAlchemy Session

    返回：
        True 如果所有玩家都提交了，False 否則
    """
    from models import Round, Player  # 避免 circular import

    # 1. 找出回合所屬的房間
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        return False

    # 2. 計算房間內非 Host 玩家數量
    player_count = db.query(Player).filter(
        Player.room_id == round_obj.room_id,
        Player.is_host == False
    ).count()

    # 3. 計算此回合的 Action 數量
    action_count = db.query(Action).filter(Action.round_id == round_id).count()

    # 4. 比較
    return action_count == player_count
