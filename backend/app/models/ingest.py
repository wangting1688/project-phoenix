"""
数据采集审计模型

阶段五 · Iteration-1
存储手工/插件/官方API 上报的日快照原始数据，供审计、幂等与增量分析。
"""

from sqlalchemy import Column, Integer, String, JSON, ForeignKey, UniqueConstraint

from app.core.database import Base
from app.core.base_model import BaseModel


class DailyIngestSnapshot(Base, BaseModel):
    """
    日粒度数据采集快照

    唯一键：(publish_record_id, snapshot_date, source_mode)
    同日同渠道重复上报走 update；跨渠道并存以便对账。
    """
    __tablename__ = "daily_ingest_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "publish_record_id", "snapshot_date", "source_mode",
            name="uq_ingest_record_date_mode",
        ),
    )

    publish_record_id = Column(Integer, ForeignKey("video_publish_records.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    platform = Column(String(50), index=True, nullable=False)
    snapshot_date = Column(String(10), index=True, nullable=False)  # YYYY-MM-DD

    source_mode = Column(String(20), index=True, nullable=False)  # manual / browser / official_api
    source_client = Column(String(100), nullable=True)

    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    private_message_count = Column(Integer, default=0)

    raw_payload = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<DailyIngestSnapshot(record={self.publish_record_id}, date={self.snapshot_date}, mode={self.source_mode})>"
