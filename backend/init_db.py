"""
数据库初始化脚本 - 创建测试用户

运行方式：
python init_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, Base, engine
from app.models import User, Role
from app.core.security import get_password_hash


def init_db():
    """初始化数据库"""
    print("正在初始化数据库...")

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # 创建测试角色
        roles = ['admin', 'creator', 'viewer']
        for role_name in roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name, description=f"{role_name}角色")
                db.add(role)
                print(f"创建角色: {role_name}")

        db.commit()

        # 创建测试用户
        test_users = [
            {
                'phone': '13800138000',
                'password': '123456',
                'nickname': '测试主播',
                'role': 'creator',
            },
            {
                'phone': '13900139000',
                'password': '123456',
                'nickname': '管理员',
                'role': 'admin',
            },
        ]

        for user_data in test_users:
            existing_user = db.query(User).filter(User.phone == user_data['phone']).first()
            if existing_user:
                print(f"用户已存在: {user_data['phone']}")
                continue

            role = db.query(Role).filter(Role.name == user_data['role']).first()
            if not role:
                role = db.query(Role).filter(Role.name == 'creator').first()

            user = User(
                phone=user_data['phone'],
                password_hash=get_password_hash(user_data['password']),
                nickname=user_data['nickname'],
                role_id=role.id if role else None,
            )
            db.add(user)
            print(f"创建用户: {user_data['phone']}")

        db.commit()
        print("\n初始化完成！")
        print("=" * 40)
        print("测试账号：")
        print("手机: 13800138000")
        print("密码: 123456")
        print("角色: 测试主播")
        print("-" * 40)
        print("手机: 13900139000")
        print("密码: 123456")
        print("角色: 管理员")
        print("=" * 40)

    except Exception as e:
        print(f"初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()