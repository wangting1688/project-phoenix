"""
用户声纹档案 - 火山方舟豆包语音 Voice Cloning

每个用户最多 3 个声纹 (业务规则, 软删除)
"""
from sqlalchemy import Column, String, Integer, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class UserVoiceProfile(Base, BaseModel):
    """用户自定义声纹档案"""
    __tablename__ = "user_voice_profiles"

    user_id = Column(Integer, index=True, nullable=False)

    # 用户起的名字 (e.g. "我的标准女声")
    name = Column(String(100), nullable=False)

    # 火山方舟 custom_speaker_id (8-256 字符, 数字/大小写字母/-/_, 字母开头)
    # 训练成功后由火山返回, 训练前为空
    custom_speaker_id = Column(String(256), index=True, nullable=True)

    # 样本文件本地路径 (storage/voice_samples/{user_id}/{profile_id}.mp3)
    sample_path = Column(String(500), nullable=False)
    sample_duration = Column(Integer)  # 样本时长 (秒)

    # 训练参数
    language = Column(Integer, default=0)  # 0=cn
    reference_text = Column(Text)  # 用户念的参考文本 (WER 校验用)
    demo_text = Column(Text)  # 试听文本 (4-300 字)

    # 状态
    # training: 样本已上传, 等训练
    # active: 训练成功, 可用
    # failed: 训练失败
    # deleted: 软删
    status = Column(String(20), default="training", index=True)

    # 火山返回的状态码
    # 0=NotFound, 1=Training, 2=Success, 3=Failed, 4=Active
    volc_status = Column(Integer, default=0)

    # 剩余训练次数 (火山返回)
    available_training_times = Column(Integer, default=0)

    # 试听音频本地路径 (训练成功后保存)
    demo_audio_path = Column(String(500), nullable=True)

    # 错误信息
    error_message = Column(String(500), nullable=True)
