"""
数据采集服务

阶段五 · Iteration-1
统一入口：手工上传 / 浏览器插件 / 官方API 三条渠道都走本服务，
写入策略：
- video_publish_records 存最新累计值（upsert）
- daily_ingest_snapshots 存日增量（幂等键 publish_record_id + date + mode）
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_performance import VideoMasterContent, VideoPublishRecord
from app.models.ingest import DailyIngestSnapshot


CORE_METRIC_FIELDS = ("views", "likes", "comments", "favorites", "shares")
EXTRA_METRIC_FIELDS = (
    "private_message_count",
    "completion_rate",
    "first_3_second_retention",
    "first_5_second_retention",
    "avg_watch_time",
    "follows",
    "exposures",
    "reach",
    "profile_visits",
)


class IngestService:
    def __init__(self, db: Optional[Session] = None):
        if db is not None:
            self.db = db
            self._owns_db = False
        else:
            self.db = SessionLocal()
            self._owns_db = True

    def close(self):
        if self._owns_db:
            self.db.close()

    # ==================== 视频登记 ====================

    def register_video(
        self,
        user_id: int,
        platform: str,
        title: str,
        publish_url: Optional[str] = None,
        publish_time: Optional[datetime] = None,
        video_master_id: Optional[int] = None,
        script_content: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> VideoPublishRecord:
        """
        登记一条视频到某平台。

        若未指定 video_master_id 则自动新建 VideoMasterContent；
        同 (video_id, platform, publish_url) 视为同一记录，命中则复用。
        """
        if video_master_id:
            master = self.db.query(VideoMasterContent).filter(
                VideoMasterContent.id == video_master_id,
                VideoMasterContent.user_id == user_id,
            ).first()
            if not master:
                raise ValueError(f"video_master_id={video_master_id} 不存在或无权访问")
        else:
            master = VideoMasterContent(
                user_id=user_id,
                title=title,
                script_content=script_content,
                duration=duration or 0,
                status="published",
            )
            self.db.add(master)
            self.db.flush()

        record_q = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_id == master.id,
            VideoPublishRecord.platform == platform,
        )
        if publish_url:
            record_q = record_q.filter(VideoPublishRecord.publish_url == publish_url)
        record = record_q.first()

        if record is None:
            record = VideoPublishRecord(
                video_id=master.id,
                user_id=user_id,
                platform=platform,
                publish_url=publish_url,
                publish_time=publish_time,
                publish_status="published",
            )
            self.db.add(record)
            self.db.flush()

        self.db.commit()
        self.db.refresh(record)
        return record

    # ==================== 日快照上报 ====================

    def record_daily_snapshot(
        self,
        user_id: int,
        publish_record_id: int,
        payload: Dict[str, Any],
        source_mode: str = "manual",
        source_client: Optional[str] = None,
        snapshot_date: Optional[str] = None,
    ) -> DailyIngestSnapshot:
        """
        写入一条日快照，同时把累计指标 upsert 到 VideoPublishRecord。

        payload 支持的字段：views/likes/comments/favorites/shares 必填其一，
        其余（private_message_count、completion_rate、top_comments 等）可选。
        """
        record = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.id == publish_record_id,
            VideoPublishRecord.user_id == user_id,
        ).first()
        if not record:
            raise ValueError(f"publish_record_id={publish_record_id} 不存在或无权访问")

        core_present = [k for k in CORE_METRIC_FIELDS if payload.get(k) is not None]
        if not core_present:
            raise ValueError("payload 必须包含至少一项核心指标（views/likes/comments/favorites/shares）")

        snap_date = snapshot_date or date.today().isoformat()

        snapshot = self.db.query(DailyIngestSnapshot).filter(
            DailyIngestSnapshot.publish_record_id == publish_record_id,
            DailyIngestSnapshot.snapshot_date == snap_date,
            DailyIngestSnapshot.source_mode == source_mode,
        ).first()

        if snapshot is None:
            snapshot = DailyIngestSnapshot(
                publish_record_id=publish_record_id,
                user_id=user_id,
                platform=record.platform,
                snapshot_date=snap_date,
                source_mode=source_mode,
                source_client=source_client,
            )
            self.db.add(snapshot)

        for field in CORE_METRIC_FIELDS:
            if payload.get(field) is not None:
                setattr(snapshot, field, int(payload[field]))
        if payload.get("private_message_count") is not None:
            snapshot.private_message_count = int(payload["private_message_count"])
        snapshot.source_client = source_client or snapshot.source_client
        snapshot.raw_payload = payload

        # upsert 累计值到 video_publish_records
        for field in CORE_METRIC_FIELDS:
            if payload.get(field) is not None:
                setattr(record, field, int(payload[field]))
        for field in EXTRA_METRIC_FIELDS:
            if payload.get(field) is not None:
                value = payload[field]
                if field in ("completion_rate", "first_3_second_retention",
                             "first_5_second_retention", "avg_watch_time"):
                    setattr(record, field, float(value))
                else:
                    setattr(record, field, int(value))
        record.data_updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    # ==================== 快照查询 ====================

    def list_snapshots(
        self,
        user_id: int,
        publish_record_id: int,
        limit: int = 30,
    ) -> List[DailyIngestSnapshot]:
        record = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.id == publish_record_id,
            VideoPublishRecord.user_id == user_id,
        ).first()
        if not record:
            raise ValueError(f"publish_record_id={publish_record_id} 不存在或无权访问")

        return (
            self.db.query(DailyIngestSnapshot)
            .filter(DailyIngestSnapshot.publish_record_id == publish_record_id)
            .order_by(DailyIngestSnapshot.snapshot_date.desc())
            .limit(limit)
            .all()
        )
