"""
Player API Endpoints

職責：
1. 玩家加入房間
2. 查詢玩家資訊
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from database import get_db
from models import Player, RoomStatus
from schemas import PlayerJoin, PlayerResponse
from core.room_manager import RoomManager
from core.exceptions import RoomNotFound, RoomNotAcceptingPlayers
from services.naming_service import generate_display_name

router = APIRouter(prefix="/api/rooms", tags=["players"])
logger = logging.getLogger(__name__)


@router.post("/{code}/join", response_model=PlayerResponse)
def join_room(code: str, player_data: PlayerJoin, db: Session = Depends(get_db)):
    """
    加入房間（玩家 endpoint）

    前置條件：
    - 房間必須存在
    - 房間狀態必須是 WAITING（尚未開始遊戲）

    流程：
    1. 透過房間代碼找到 Room
    2. 檢查房間是否接受新玩家
    3. 生成顯示名稱（例如：狐狸 1）
    4. 建立 Player
    5. 返回玩家資訊
    """
    try:
        # 1. 找到房間
        room = RoomManager.get_room_by_code(db, code)

        # 2. 檢查房間狀態
        if room.status != RoomStatus.WAITING:
            raise RoomNotAcceptingPlayers(
                f"Room {code} is not accepting players (status: {room.status.value})"
            )

        # 3. 生成顯示名稱
        display_name = generate_display_name(room.id, db)

        # 4. 建立玩家
        player = Player(
            room_id=room.id,
            nickname=player_data.nickname,
            display_name=display_name,
            is_host=False
        )
        db.add(player)
        db.commit()
        db.refresh(player)

        logger.info(
            f"Player {player.id} ({player.nickname}) joined room {room.id} as {display_name}"
        )

        return PlayerResponse(
            player_id=player.id,
            room_id=room.id,
            display_name=player.display_name
        )

    except RoomNotFound:
        raise HTTPException(status_code=404, detail="Room not found")
    except RoomNotAcceptingPlayers as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to join room: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error")
