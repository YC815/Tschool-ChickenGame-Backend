"""
並發控制工具

提供 Database-level 的鎖定機制，防止競態條件（Race Condition）

主要使用 PostgreSQL 的 SELECT ... FOR UPDATE 來實現悲觀鎖（Pessimistic Locking）
"""
from sqlalchemy.orm import Session, Query
from uuid import UUID

from models import Room, Round


def with_room_lock(room_id: UUID, db: Session) -> Query:
    """
    鎖定一個 Room（行級鎖）

    使用場景：
    - 修改 Room 狀態時
    - 需要確保 Room 在整個 transaction 期間不被其他請求修改

    範例：
        room = with_room_lock(room_id, db).first()
        if not room:
            raise RoomNotFound(room_id)
        room.status = RoomStatus.PLAYING
        db.commit()

    參數：
        room_id: Room 的 UUID
        db: SQLAlchemy Session

    返回：
        Query object（需要呼叫 .first() 或 .one() 來取得結果）

    注意：
        - nowait=False 表示如果鎖被佔用，會等待（避免 deadlock）
        - 必須在 transaction 內使用（確保有 commit 或 rollback）
    """
    return db.query(Room).filter(
        Room.id == room_id
    ).with_for_update(nowait=False)


def with_round_lock(round_id: UUID, db: Session) -> Query:
    """
    鎖定一個 Round（行級鎖）

    使用場景：
    - 檢查並修改 Round 狀態時
    - 計算結果時（防止重複計算）
    - 需要確保 Round 在整個 transaction 期間不被其他請求修改

    範例：
        round_obj = with_round_lock(round_id, db).first()
        if round_obj and not round_obj.result_calculated:
            # 計算結果...
            round_obj.result_calculated = True
            db.commit()

    參數：
        round_id: Round 的 UUID
        db: SQLAlchemy Session

    返回：
        Query object（需要呼叫 .first() 或 .one() 來取得結果）
    """
    return db.query(Round).filter(
        Round.id == round_id
    ).with_for_update(nowait=False)


def lock_multiple_rounds(round_ids: list[UUID], db: Session) -> Query:
    """
    鎖定多個 Rounds（用於批次操作）

    使用場景：
    - 需要同時處理多個回合的操作
    - 確保操作的原子性

    參數：
        round_ids: Round UUID 列表
        db: SQLAlchemy Session

    返回：
        Query object（呼叫 .all() 取得所有結果）
    """
    return db.query(Round).filter(
        Round.id.in_(round_ids)
    ).with_for_update(nowait=False)
