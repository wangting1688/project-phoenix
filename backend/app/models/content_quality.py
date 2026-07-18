from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Enum
import enum

from app.core.database import Base
from app.core.base_model import BaseModel


class RiskLevel(str, enum.Enum):
    """风险等级"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DANGER = "danger"


class ContentType(str, enum.Enum):
    """审核内容类型"""
    OPPORTUNITY = "opportunity"
    SCRIPT = "script"
    VIDEO = "video"


class ContentReview(Base, BaseModel):
    """内容审核表 - 记录AI质量控制结果"""
    __tablename__ = "content_reviews"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 审核对象
    content_type = Column(String(50), nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)

    # 四大维度评分
    health_score = Column(Integer, default=0)
    marketing_score = Column(Integer, default=0)
    viral_score = Column(Integer, default=0)
    conversion_score = Column(Integer, default=0)
    originality_score = Column(Integer, default=0)

    # 综合评分
    final_score = Column(Integer, default=0)
    risk_level = Column(String(20), default="safe")

    # AI审核详情
    health_analysis = Column(JSON, nullable=True)
    marketing_analysis = Column(JSON, nullable=True)
    viral_analysis = Column(JSON, nullable=True)
    conversion_analysis = Column(JSON, nullable=True)

    # 优化建议
    suggestions = Column(JSON, nullable=True)
    auto_fixes = Column(JSON, nullable=True)

    # 状态
    status = Column(String(50), default="pending", index=True)
    reviewed_by = Column(String(50), default="ai")

    def __repr__(self):
        return f"<ContentReview(content_type={self.content_type}, content_id={self.content_id}, final_score={self.final_score})>"


class QualityRule(Base, BaseModel):
    """质量控制规则表 - 自定义审核规则"""
    __tablename__ = "quality_rules"

    rule_type = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 规则配置
    keywords_forbid = Column(JSON, nullable=True)
    keywords_warn = Column(JSON, nullable=True)
    patterns = Column(JSON, nullable=True)

    # 权重和阈值
    weight = Column(Integer, default=1)
    threshold = Column(Integer, default=60)

    # 生效范围
    category = Column(String(100), nullable=True)
    is_active = Column(Integer, default=1)

    def __repr__(self):
        return f"<QualityRule(rule_type={self.rule_type}, name={self.name})>"