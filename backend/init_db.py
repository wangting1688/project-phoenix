"""
种子数据脚本 - 创建本地测试账号

前置条件：
    1. 已配置 .env
    2. 已执行 `alembic upgrade head` 建好数据表

运行方式：
    python init_db.py

安全约束：
    仅在 DEBUG=true 时允许运行，避免误在生产环境写入测试账号。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.core.security import get_password_hash


def init_db():
    if not settings.DEBUG:
        print("[abort] DEBUG=false，禁止在非调试环境执行 init_db。")
        sys.exit(1)

    print("正在写入种子数据（本地测试账号）...")

    db = SessionLocal()

    try:
        test_users = [
            {"phone": "13800138000", "password": "123456", "nickname": "测试主播"},
            {"phone": "13900139000", "password": "123456", "nickname": "管理员"},
        ]

        for user_data in test_users:
            existing_user = db.query(User).filter(User.phone == user_data["phone"]).first()
            if existing_user:
                print(f"用户已存在: {user_data['phone']}")
                continue

            user = User(
                phone=user_data["phone"],
                password_hash=get_password_hash(user_data["password"]),
                nickname=user_data["nickname"],
            )
            db.add(user)
            print(f"创建用户: {user_data['phone']}")

        db.commit()
        print("\n初始化完成！")
        print("=" * 40)
        print("本地测试账号（仅 DEBUG 环境）：")
        print("手机: 13800138000  密码: 123456  昵称: 测试主播")
        print("手机: 13900139000  密码: 123456  昵称: 管理员")
        print("=" * 40)

    except Exception as e:
        print(f"初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
