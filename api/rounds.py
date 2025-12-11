"""
Round API Endpoints - 短輪詢版

重點：
1. submit_action 冪等，並在 state_version 上反映進度
2. 所有業務邏輯集中在 RoundManager
3. WebSocket 全面移除，前端靠 /state 獲取更新
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import logging

from database import get_db
from models import Round, Player, Action, Message, RoundStatus, Choice
from schemas import (
    RoundCurrentResponse,
    PairResponse,
    ActionSubmit,
    ActionResponse,
    RoundResultResponse,
    MessageSubmit,
    MessageResponse,
    IndicatorResponse
)
from core.round_manager import RoundManager
from core.room_manager import RoomManager
from core.exceptions import (
    RoundNotFound,
    MessageNotAllowedInThisRound,
    MessageAlreadySent,
    IndicatorsAlreadyAssigned,
    InvalidStateTransition
)
from services.pairing_service import get_opponent_id
from services.indicator_service import (
    assign_indicators,
    get_player_indicator,
    indicators_already_assigned
)
from services.round_phase_service import is_message_round
from services.state_service import bump_state_version

router = APIRouter(prefix="/api/rooms", tags=["rounds"])
logger = logging.getLogger(__name__)


@router.get("/{room_id}/rounds/current", response_model=RoundCurrentResponse)
def get_current_round(room_id: str, db: Session = Depends(get_db)):
    """
    取得當前回合資訊

    返回：
        - round_number: 回合數
        - phase: 回合階段（NORMAL/MESSAGE/INDICATOR）
        - status: 回合狀態（WAITING_ACTIONS/CALCULATING/COMPLETED）
    """
    try:
        current_round = RoundManager.get_current_round(db, room_id)
        if not current_round:
            raise HTTPException(status_code=404, detail="No active round")

        return RoundCurrentResponse(
            round_number=current_round.round_number,
            phase=current_round.phase,
            status=current_round.status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/{room_id}/rounds/{round_number}/pair", response_model=PairResponse)
def get_player_pair(
    room_id: str,
    round_number: int,
    player_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    取得玩家在某回合的對手資訊

    參數：
        room_id: 房間 UUID
        round_number: 回合數
        player_id: 玩家 UUID（query parameter）

    返回：
        - opponent_id: 對手 UUID
        - opponent_display_name: 對手顯示名稱
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 2. 找到對手 ID
        opponent_id = get_opponent_id(round_obj.id, player_id, db)

        # 3. 取得對手資訊
        opponent = db.query(Player).filter(Player.id == opponent_id).first()
        if not opponent:
            raise HTTPException(status_code=404, detail="Opponent not found")

        return PairResponse(
            opponent_id=opponent_id,
            opponent_display_name=opponent.display_name
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get pair: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{room_id}/rounds/{round_number}/action", response_model=ActionResponse)
def submit_action(
    room_id: str,
    round_number: int,
    action_data: ActionSubmit,
    db: Session = Depends(get_db)
):
    """
    提交玩家動作（核心重構！）

    **重大改動**：
    1. 使用 RoundManager.submit_action() - 冪等性設計
    2. 呼叫 RoundManager.try_finalize_round() - 安全的並發設計
    3. 狀態更新改由 state_version 控制，前端靠短輪詢 /state 更新畫面

    **消除特殊情況**：
    - 舊版：「最後一個人觸發結算」- 有特殊邏輯
    - 新版：「任何人都嘗試結算」- 沒有特殊情況

    **並發安全**：
    - DB lock 確保不會重複計算
    - 冪等性確保重複提交不會出錯

    流程：
    1. 找到回合
    2. 提交動作（冪等）
    3. 嘗試結算（冪等）

    參數：
        room_id: 房間 UUID
        round_number: 回合數
        action_data: 包含 player_id 和 choice

    返回：
        - status: "ok"
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        logger.info(
            f"Submitting action for player {action_data.player_id} "
            f"in round {round_number} (room={room_id}): {action_data.choice.value}"
        )

        # 2. 提交動作（冪等：重複提交會返回既有 Action）
        action, created_new = RoundManager.submit_action(
            db,
            round_obj.id,
            action_data.player_id,
            action_data.choice
        )
        logger.info(
            "Action %s for player %s in round %s (room=%s)",
            "created" if created_new else "reused",
            action_data.player_id,
            round_number,
            room_id
        )

        # 3. 嘗試計算回合結果（冪等：重複呼叫不會重複計算）
        #    注意：這裡只計算，不公布結果
        finalized = RoundManager.try_finalize_round(db, round_obj.id)

        return ActionResponse(status="ok")

    except RoundNotFound:
        raise HTTPException(status_code=404, detail="Round not found")
    except Exception as e:
        logger.error(f"Failed to submit action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{room_id}/rounds/{round_number}/publish", response_model=ActionResponse)
def publish_round_results(
    room_id: str,
    round_number: int,
    db: Session = Depends(get_db)
):
    """
    公布回合結果（Host endpoint）

    前置條件：
    - Round 狀態必須是 READY_TO_PUBLISH

    效果：
    - 狀態轉換 READY_TO_PUBLISH -> COMPLETED
    - 客戶端透過 /state 得知 COMPLETED 後再呼叫 GET /rounds/{n}/result

    參數：
        room_id: 房間 UUID
        round_number: 回合數

    返回：
        - status: "ok"
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 2. 公布結果（冪等）
        RoundManager.publish_round(db, round_obj.id)

        logger.info(f"Round {round_number} published for room {room_id}")
        return ActionResponse(status="ok")

    except InvalidStateTransition as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to publish round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{room_id}/rounds/{round_number}/skip", response_model=ActionResponse)
def skip_round(
    room_id: str,
    round_number: int,
    db: Session = Depends(get_db)
):
    """
    跳過回合（Host endpoint）

    用途：
    - 有玩家斷線、長時間不選擇
    - 管理員決定提前結束

    效果：
    - 為未提交的玩家填入預設選擇（TURN）
    - 計算結果
    - 立即公布

    參數：
        room_id: 房間 UUID
        round_number: 回合數

    返回：
        - status: "ok"
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 2. 檢查狀態（只能跳過 WAITING_ACTIONS 或 READY_TO_PUBLISH）
        if round_obj.status not in [RoundStatus.WAITING_ACTIONS, RoundStatus.READY_TO_PUBLISH]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot skip round in status {round_obj.status.value}"
            )

        logger.info(f"Skipping round {round_number} for room {room_id}")

        # 3. 為未提交的玩家填入預設動作
        from services.pairing_service import get_pairs_in_round
        pairs = get_pairs_in_round(round_obj.id, db)

        for pair in pairs:
            for player_id in [pair.player1_id, pair.player2_id]:
                # 檢查該玩家是否已提交
                existing = db.query(Action).filter(
                    Action.round_id == round_obj.id,
                    Action.player_id == player_id
                ).first()

                if not existing:
                    # 預設選擇：TURN（轉彎）
                    logger.info(f"Auto-submitting TURN for player {player_id}")
                    RoundManager.submit_action(
                        db, round_obj.id, player_id, Choice.TURN
                    )

        # 4. 計算結果（如果還沒計算）
        if round_obj.status == RoundStatus.WAITING_ACTIONS:
            RoundManager.try_finalize_round(db, round_obj.id)

        # 5. 立即公布結果
        RoundManager.publish_round(db, round_obj.id)

        logger.info(f"Round {round_number} skipped and published for room {room_id}")
        return ActionResponse(status="ok")

    except Exception as e:
        logger.error(f"Failed to skip round: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/{room_id}/rounds/{round_number}/result", response_model=RoundResultResponse)
def get_round_result(
    room_id: str,
    round_number: int,
    player_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    取得回合結果

    前置條件：
    - 回合必須已結算（status=COMPLETED）

    返回：
        - opponent_display_name: 對手顯示名稱
        - your_choice: 你的選擇
        - opponent_choice: 對手的選擇
        - your_payoff: 你的分數
        - opponent_payoff: 對手的分數
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 2. 找到玩家的 Action
        player_action = db.query(Action).filter(
            Action.round_id == round_obj.id,
            Action.player_id == player_id
        ).first()

        if not player_action or player_action.payoff is None:
            raise HTTPException(status_code=404, detail="Result not available yet")

        # 3. 找到對手
        opponent_id = get_opponent_id(round_obj.id, player_id, db)
        opponent = db.query(Player).filter(Player.id == opponent_id).first()
        opponent_action = db.query(Action).filter(
            Action.round_id == round_obj.id,
            Action.player_id == opponent_id
        ).first()

        if not opponent or not opponent_action:
            raise HTTPException(status_code=500, detail="Opponent data not found")

        return RoundResultResponse(
            opponent_display_name=opponent.display_name,
            your_choice=player_action.choice,
            opponent_choice=opponent_action.choice,
            your_payoff=player_action.payoff,
            opponent_payoff=opponent_action.payoff
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get round result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{room_id}/rounds/{round_number}/message", response_model=ActionResponse)
def send_message(
    room_id: str,
    round_number: int,
    message_data: MessageSubmit,
    db: Session = Depends(get_db)
):
    """
    發送訊息給對手（Round 5-6 限定）

    前置條件：
    - 必須是 Round 5 或 6
    - 玩家只能發送一次訊息

    流程：
    1. 檢查回合數
    2. 找到對手
    3. 建立 Message
    4. state_version 會提升，前端透過短輪詢看到新訊息
    """
    try:
        # 1. 檢查是否為訊息回合
        if not is_message_round(round_number):
            raise MessageNotAllowedInThisRound(
                f"Messages are only allowed in Round 5-6, got round {round_number}"
            )

        # 2. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 3. 找到對手
        receiver_id = get_opponent_id(round_obj.id, message_data.sender_id, db)

        # 4. 檢查是否已發送過
        existing = db.query(Message).filter(
            Message.round_id == round_obj.id,
            Message.sender_id == message_data.sender_id
        ).first()

        if existing:
            raise MessageAlreadySent("You have already sent a message in this round")

        # 5. 建立訊息
        message = Message(
            room_id=room_id,
            round_id=round_obj.id,
            sender_id=message_data.sender_id,
            receiver_id=receiver_id,
            content=message_data.content
        )
        db.add(message)
        bump_state_version(db, room_id, reason="message_sent")
        db.commit()

        return ActionResponse(status="ok")

    except (MessageNotAllowedInThisRound, MessageAlreadySent) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send message: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/{room_id}/rounds/{round_number}/message", response_model=MessageResponse)
def get_message(
    room_id: str,
    round_number: int,
    player_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    取得對手發送的訊息

    參數：
        room_id: 房間 UUID
        round_number: 回合數
        player_id: 玩家 UUID（接收者）

    返回：
        - content: 訊息內容
        - from_opponent: True（固定值）
    """
    try:
        # 1. 找到回合
        round_obj = RoundManager.get_round_by_number(db, room_id, round_number)
        if not round_obj:
            raise HTTPException(status_code=404, detail="Round not found")

        # 2. 找到訊息
        message = db.query(Message).filter(
            Message.round_id == round_obj.id,
            Message.receiver_id == player_id
        ).first()

        if not message:
            raise HTTPException(status_code=404, detail="No message found")

        return MessageResponse(content=message.content, from_opponent=True)

    except HTTPException:
        # 讓 4xx 直接透出，避免被包成 500
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{room_id}/indicators/assign", response_model=ActionResponse)
def assign_indicators_endpoint(room_id: str, db: Session = Depends(get_db)):
    """
    分配指標（Host endpoint，Round 6 之後）

    前置條件：
    - 當前回合 >= 6
    - 尚未分配過指標

    流程：
    1. 檢查是否已分配
    2. 呼叫 IndicatorService.assign_indicators()
    3. 發送 WebSocket 通知
    """
    try:
        # 1. 檢查房間
        room = RoomManager.get_room_by_id(db, room_id)

        # 2. 檢查回合數
        if room.current_round < 6:
            raise HTTPException(
                status_code=400,
                detail="Indicators can only be assigned after Round 6"
            )

        # 3. 檢查是否已分配
        if indicators_already_assigned(room_id, db):
            raise IndicatorsAlreadyAssigned("Indicators already assigned")

        # 4. 分配指標並提升版本
        assign_indicators(room_id, db)
        bump_state_version(db, room_id, reason="indicators_assigned")
        db.commit()

        return ActionResponse(status="ok")

    except IndicatorsAlreadyAssigned as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to assign indicators: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/{room_id}/indicator", response_model=IndicatorResponse)
def get_player_indicator_endpoint(
    room_id: str,
    player_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    取得玩家的指標符號

    參數：
        room_id: 房間 UUID
        player_id: 玩家 UUID

    返回：
        - symbol: 指標符號（例如：🍋）
    """
    try:
        symbol = get_player_indicator(player_id, db)
        return IndicatorResponse(symbol=symbol)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get indicator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")
