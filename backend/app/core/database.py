from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

db_url = settings.DATABASE_URL
connect_args = {}
engine_kwargs = {"echo": settings.DEBUG}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # SQLite 是本地文件，建连接只是拿一个文件句柄，池化收益极低；
    # 而默认 QueuePool(size=5, max_overflow=10) 只给 15 个并发连接。
    # 作品页一次要拉几十张封面/视频，每个 /media/sign 都要开一个 session，
    # 瞬间打满连接池 → 其余请求排队 30s 后抛 QueuePool TimeoutError
    # → 499/500 → 前端 Promise.all 全盘失败 → 整页封面空白、点了没反应。
    # 改用 NullPool：连接随用随开随关，从根上消除「连接池耗尽」这一类故障。
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)


# SQLite 下开启 WAL + busy_timeout：允许并发读、写者串行但不再瞬时死锁。
# MySQL 等其他方言时该钩子不生效。
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragma_on_connect(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
