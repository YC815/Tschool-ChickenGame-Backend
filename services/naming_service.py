"""
命名服務：生成 Room Code 和 Player Display Name

純計算邏輯，不涉及狀態轉換
"""
import random
import string

from sqlalchemy.orm import Session

from models import Room, Player


def generate_room_code() -> str:
    """
    生成隨機的 6 位大寫字母房間代碼

    範例：ABCDEF, XYZABC

    注意：
    - 不檢查唯一性（由呼叫者負責）
    - 26^6 = 308,915,776 種可能，碰撞機率極低
    """
    return ''.join(random.choices(string.ascii_uppercase, k=6))


def generate_display_name(room_id: str, db: Session) -> str:
    """
    為房間內的新玩家生成顯示名稱

    格式：「動物 N」
    範例：狐狸 1, 老鷹 1, 熊 1, ..., 狐狸 2, 老鷹 2, ...

    邏輯：
    - 有 10 種動物
    - 玩家按照加入順序分配動物
    - 如果超過 10 人，數字遞增（狐狸 1, 狐狸 2, ...）

    參數：
        room_id: 房間 ID
        db: SQLAlchemy Session

    返回：
        顯示名稱字串

    範例：
        第 1 位玩家: 狐狸 1
        第 2 位玩家: 老鷹 1
        ...
        第 11 位玩家: 狐狸 2
    """
    animals = ["狐狸", "老鷹", "熊", "虎", "狼", "鹿", "豹", "獅", "兔", "蛇"]

    # 查詢房間內現有玩家數量（不包含 Host）
    existing_players = db.query(Player).filter(
        Player.room_id == room_id,
        Player.is_host == False
    ).all()
    count = len(existing_players)

    # 計算動物和數字
    animal = animals[count % len(animals)]
    number = (count // len(animals)) + 1

    return f"{animal} {number}"
