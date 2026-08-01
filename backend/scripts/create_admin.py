"""
创建/提升总部管理员 (super_admin)

背景:
    公开注册接口硬编码 role="anchor", 渠道商管理接口又要求 super_admin,
    形成自举死锁。本脚本是唯一的管理员创建入口, 只能在服务器本地执行。

运行方式:
    cd /www/phoenix/backend
    .venv/bin/python scripts/create_admin.py --phone 18663791085

安全约束:
    - 密码仅通过交互式输入 (不回显), 不接受命令行参数, 避免进入 shell history
    - 全程不打印、不写入密码明文
    - 手机号已存在时, 需显式确认是否提升角色 / 重置密码
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User

MIN_PASSWORD_LEN = 8


def validate_password(pwd: str) -> str:
    """返回错误说明; 通过则返回空字符串"""
    if len(pwd) < MIN_PASSWORD_LEN:
        return f"密码至少 {MIN_PASSWORD_LEN} 位"
    if pwd.isdigit():
        return "密码不能是纯数字"
    if pwd.isalpha():
        return "密码不能是纯字母, 请混合数字或符号"
    if pwd.lower() in ("password", "12345678", "admin123"):
        return "密码过于常见"
    return ""


def prompt_password() -> str:
    """交互式两次输入密码, 不回显"""
    for _ in range(3):
        pwd = getpass.getpass("请输入管理员密码 (输入时不显示): ")
        err = validate_password(pwd)
        if err:
            print(f"  ✗ {err}\n")
            continue
        again = getpass.getpass("请再次输入以确认: ")
        if pwd != again:
            print("  ✗ 两次输入不一致\n")
            continue
        return pwd
    print("✗ 尝试次数过多, 已退出")
    sys.exit(1)


def confirm(question: str) -> bool:
    return input(f"{question} [y/N]: ").strip().lower() in ("y", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建或提升总部管理员")
    parser.add_argument("--phone", required=True, help="管理员登录手机号")
    parser.add_argument("--nickname", default="总部管理员", help="显示昵称")
    args = parser.parse_args()

    phone = args.phone.strip()
    if not (phone.isdigit() and len(phone) == 11):
        print("✗ 手机号需为 11 位数字")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.phone == phone).first()

        if existing:
            print(f"该手机号已存在: id={existing.id}, 当前角色={existing.role}, "
                  f"tenant_id={existing.tenant_id}")
            if existing.role == "super_admin":
                if not confirm("已是总部管理员, 是否重置密码?"):
                    print("已取消")
                    return
                existing.password_hash = get_password_hash(prompt_password())
                db.commit()
                print(f"✓ 密码已重置 (账号 {phone})")
                return

            if not confirm("是否提升为总部管理员并重置密码?"):
                print("已取消")
                return
            existing.role = "super_admin"
            # 总部管理员不属于任何渠道商, 否则会被租户过期校验拦下
            existing.tenant_id = None
            existing.status = 1
            existing.password_hash = get_password_hash(prompt_password())
            db.commit()
            print(f"✓ 已提升为总部管理员 (账号 {phone}, id={existing.id})")
            return

        print(f"将创建新的总部管理员: {phone}")
        password = prompt_password()
        user = User(
            phone=phone,
            password_hash=get_password_hash(password),
            nickname=args.nickname,
            role="super_admin",
            tenant_id=None,
            status=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✓ 总部管理员已创建 (账号 {phone}, id={user.id}, role={user.role})")

    finally:
        db.close()


if __name__ == "__main__":
    main()
