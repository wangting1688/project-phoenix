"""
Three Version Production Service - 三版本生产服务

TASK-016.3B.4：AI Growth Review Memory

核心职责：
1. 同一视频素材生成三个不同商业化程度的版本
2. 支持涨粉版、私域版、成交版
3. 共享素材资产，差异化配置
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import VideoProductionJob, VideoVersion
from app.models.video_edit_plan import VideoEditPlan
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.growth_quality_agent_v2 import GrowthQualityAgentV2


class ThreeVersionProductionService:
    """三版本生产服务"""

    VERSION_TYPES = {
        "growth": {
            "name": "纯涨粉版",
            "commercial_pressure": "<30",
            "purpose": "自然流量增长，粉丝沉淀",
        },
        "private_traffic": {
            "name": "私域引流版",
            "commercial_pressure": "30-50",
            "purpose": "引导评论/私信/主页访问",
        },
        "conversion": {
            "name": "成交版",
            "commercial_pressure": "50+",
            "purpose": "促进GMV转化",
        },
    }

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()
        self.growth_agent = GrowthQualityAgentV2()

    def close(self):
        self.db.close()
        self.growth_agent.close()

    def create_three_versions(self, job_id: int) -> Dict[str, Any]:
        """为同一生产任务创建三个版本"""
        job = self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == job.source_plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        existing_versions = self.db.query(VideoVersion).filter(
            VideoVersion.production_job_id == job_id
        ).all()

        if existing_versions:
            return {
                "success": True,
                "message": "版本已存在",
                "versions": [
                    {
                        "id": v.id,
                        "version_type": v.version_type,
                        "version_name": v.version_name,
                        "status": v.status,
                    }
                    for v in existing_versions
                ],
            }

        versions = []

        for version_type, version_config in self.VERSION_TYPES.items():
            version = self._create_version(job_id, plan, version_type, version_config)
            versions.append(version)

        self.db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "versions": [
                {
                    "id": v.id,
                    "version_type": v.version_type,
                    "version_name": v.version_name,
                    "commercial_pressure_index": v.commercial_pressure_index,
                    "status": v.status,
                }
                for v in versions
            ],
        }

    def _create_version(self, job_id: int, plan: VideoEditPlan, version_type: str, config: Dict) -> VideoVersion:
        """创建单个版本"""
        commercial_pressure = self._estimate_commercial_pressure(plan, version_type)

        version = VideoVersion(
            production_job_id=job_id,
            version_type=version_type,
            version_name=config["name"],
            commercial_pressure_index=commercial_pressure,
            commercial_strategy=config["purpose"],
            status="pending",
            timeline_override=self._build_timeline_override(plan, version_type),
            config_override=self._build_config_override(plan, version_type),
        )

        self.db.add(version)
        self.db.flush()
        return version

    def _estimate_commercial_pressure(self, plan: VideoEditPlan, version_type: str) -> int:
        """估算商业压力"""
        target_pressures = {
            "growth": 20,
            "private_traffic": 40,
            "conversion": 70,
        }
        return target_pressures.get(version_type, 30)

    def _build_timeline_override(self, plan: VideoEditPlan, version_type: str) -> Dict[str, Any]:
        """构建Timeline覆盖配置"""
        if version_type == "growth":
            return {
                "remove_segments": ["conversion", "cta", "product"],
                "reorder_priority": ["hook", "knowledge", "social_proof", "emotion"],
            }
        elif version_type == "private_traffic":
            return {
                "remove_segments": ["conversion", "cta"],
                "reorder_priority": ["hook", "problem", "knowledge", "social_proof", "consultation"],
            }
        else:
            return {
                "remove_segments": [],
                "reorder_priority": ["hook", "product", "use_case", "social_proof", "conversion"],
            }

    def _build_config_override(self, plan: VideoEditPlan, version_type: str) -> Dict[str, Any]:
        """构建配置覆盖"""
        configs = {
            "growth": {
                "max_commercial_words": 0,
                "product_position": "omit",
                "cta_type": "follow",
                "emphasis": "关注理由、连续剧钩子",
                "structure": "用户兴趣 → 情绪价值 → 知识价值 → 主播人格 → 自然关注",
            },
            "private_traffic": {
                "max_commercial_words": 3,
                "product_position": "mid",
                "cta_type": "comment_or_message",
                "emphasis": "轻咨询引导、评论互动",
                "structure": "痛点 → 解决方案 → 案例 → 咨询引导",
            },
            "conversion": {
                "max_commercial_words": 10,
                "product_position": "early",
                "cta_type": "purchase",
                "emphasis": "产品介绍、信任背书、购买引导",
                "structure": "产品介绍 → 使用场景 → 案例 → 活动 → 购买入口",
            },
        }
        return configs.get(version_type, {})

    def assess_version(self, version_id: int) -> Dict[str, Any]:
        """评估单个版本"""
        version = self.db.query(VideoVersion).filter(VideoVersion.id == version_id).first()
        if not version:
            return {"success": False, "error": "版本不存在"}

        job = self.db.query(VideoProductionJob).filter(
            VideoProductionJob.id == version.production_job_id
        ).first()
        if not job:
            return {"success": False, "error": "生产任务不存在"}

        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == job.source_plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        assessment = self.growth_agent.assess_growth_quality_v2(plan.id, version.version_type)

        if assessment["success"]:
            version.growth_score = assessment["organic_growth_score"]
            self.db.commit()

        return {
            "success": True,
            "version_id": version_id,
            "version_type": version.version_type,
            "assessment": assessment,
        }

    def list_versions(self, job_id: int) -> List[Dict[str, Any]]:
        """列出所有版本"""
        versions = self.db.query(VideoVersion).filter(
            VideoVersion.production_job_id == job_id
        ).all()

        return [
            {
                "id": v.id,
                "version_type": v.version_type,
                "version_name": v.version_name,
                "commercial_pressure_index": v.commercial_pressure_index,
                "status": v.status,
                "growth_score": v.growth_score,
                "output_path": v.output_path,
            }
            for v in versions
        ]
