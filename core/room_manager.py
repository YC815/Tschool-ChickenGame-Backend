"""
Room Manager：管理 Room 的完整生命週期

職責：
1. 建立 Room（含 Host player）
2. 開始遊戲（狀態轉換 + 驗證）
3. 結束遊戲
4. 查詢 Room 資訊

Linus 原則：
- 單一職責：只管 Room，不管 Round
- 消除特殊情況：所有狀態變更經過 StateMachine
- 資料結構優先：先檢查資料是否符合要求，再執行操作
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Tuple
import logging

from models import Room, Player, RoomStatus, EventLog
from core.state_machine import RoomStateMachine
from core.locks import with_room_lock
from core.exceptions import (
    RoomNotFound,
    InvalidPlayerCount,
    InvalidStateTransition
)
from services.naming_service import generate_room_code
from database import transactional

logger = logging.getLogger(__name__)


class RoomManager:
    """Room 生命週期管理器"""

    @staticmethod
    @transactional
    def create_room(db: Session) -> Tuple[Room, Player]:
        """
        建立新房間（含 Host 玩家）

        流程：
        1. 生成唯一的房間代碼
        2. 建立 Room
        3. 建立 Host Player
        4. 記錄事件

        參數：
            db: SQLAlchemy Session

        返回：
            (Room, Host Player) tuple

        注意：
            - 使用 @transactional，自動處理 commit/rollback
            - Room code 碰撞機率極低（26^6），但仍會檢查唯一性
        """
        # 1. 生成唯一的房間代碼
        code = generate_room_code()
        while db.query(Room).filter(Room.code == code).first():
            code = generate_room_code()
            logger.warning(f"Room code collision detected, regenerating: {code}")

        # 2. 建立 Room
        room = Room(code=code, status=RoomStatus.WAITING)
        db.add(room)
        db.flush()  # 取得 room.id

        logger.info(f"Created room {room.id} with code {code}")

        # 3. 建立 Host Player
        host = Player(
            room_id=room.id,
            nickname="Host",
            display_name="Host",
            is_host=True
        )
        db.add(host)

        # 4. 記錄事件
        event = EventLog(
            room_id=room.id,
            event_type="ROOM_CREATED",
            data={"code": code}
        )
        db.add(event)

        # transactional decorator 會自動 commit
        return room, host

    @staticmethod
    @transactional
    def start_game(db: Session, room_id: UUID) -> Room:
        """
        開始遊戲（狀態轉換 WAITING -> PLAYING）

        前置條件：
        1. Room 必須存在
        2. Room 狀態必須是 WAITING
        3. 玩家數量必須 >= 2 且為偶數

        流程：
        1. 驗證前置條件
        2. 透過 StateMachine 轉換狀態
        3. 記錄事件

        參數：
            db: SQLAlchemy Session
            room_id: Room UUID

        返回：
            更新後的 Room

        異常：
            RoomNotFound: Room 不存在
            InvalidPlayerCount: 玩家數量不符合要求
            InvalidStateTransition: Room 狀態不是 WAITING
        """
        # 1. 取得並鎖定 Room
        room = with_room_lock(room_id, db).first()
        if not room:
            raise RoomNotFound(room_id)

        # 2. 驗證玩家數量
        player_count = db.query(Player).filter(
            Player.room_id == room_id,
            Player.is_host == False
        ).count()

        if player_count < 2:
            raise InvalidPlayerCount(
                f"Need at least 2 players to start game, got {player_count}"
            )

        if player_count % 2 != 0:
            raise InvalidPlayerCount(
                f"Player count must be even, got {player_count}"
            )

        logger.info(f"Starting game for room {room_id} with {player_count} players")

        # 3. 狀態轉換（會自動記錄 ROOM_STATE_CHANGED 事件）
        room = RoomStateMachine.transition(room_id, RoomStatus.PLAYING, db)

        # 4. 記錄遊戲開始事件
        event = EventLog(
            room_id=room_id,
            event_type="GAME_STARTED",
            data={"player_count": player_count}
        )
        db.add(event)

        return room

    @staticmethod
    @transactional
    def end_game(db: Session, room_id: UUID) -> Room:
        """
        結束遊戲（狀態轉換 PLAYING -> FINISHED）

        前置條件：
        1. Room 必須存在
        2. Room 狀態必須是 PLAYING

        流程：
        1. 透過 StateMachine 轉換狀態
        2. 記錄事件

        參數：
            db: SQLAlchemy Session
            room_id: Room UUID

        返回：
            更新後的 Room

        異常：
            RoomNotFound: Room 不存在
            InvalidStateTransition: Room 狀態不是 PLAYING
        """
        # 1. 狀態轉換（會自動檢查 Room 是否存在和狀態是否合法）
        room = RoomStateMachine.transition(room_id, RoomStatus.FINISHED, db)

        logger.info(f"Game ended for room {room_id}")

        # 2. 記錄遊戲結束事件
        event = EventLog(
            room_id=room_id,
            event_type="GAME_ENDED",
            data={}
        )
        db.add(event)

        return room

    @staticmethod
    def get_room_by_code(db: Session, code: str) -> Room:
        """
        透過房間代碼取得 Room

        參數：
            db: SQLAlchemy Session
            code: 6 位房間代碼

        返回：
            Room object

        異常：
            RoomNotFound: Room 不存在
        """
        room = db.query(Room).filter(Room.code == code).first()
        if not room:
            raise RoomNotFound(f"Room with code {code}")
        return room

    @staticmethod
    def get_room_by_id(db: Session, room_id: UUID) -> Room:
        """
        透過 UUID 取得 Room

        參數：
            db: SQLAlchemy Session
            room_id: Room UUID

        返回：
            Room object

        異常：
            RoomNotFound: Room 不存在
        """
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise RoomNotFound(room_id)
        return room

    @staticmethod
    def get_player_count(db: Session, room_id: UUID) -> int:
        """
        取得房間內玩家數量（不含 Host）

        參數：
            db: SQLAlchemy Session
            room_id: Room UUID

        返回：
            玩家數量
        """
        return db.query(Player).filter(
            Player.room_id == room_id,
            Player.is_host == False
        ).count()
