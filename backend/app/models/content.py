from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, DECIMAL
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class ContentProject(Base, BaseModel):
    __tablename__ = "content_projects"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    source_type = Column(String(50), index=True)
    topic = Column(String(500))
    category = Column(String(100), index=True)
    status = Column(String(50), default="draft", index=True)
    workflow_status = Column(String(100), nullable=True)

    user = relationship("User", back_populates="projects")
    contents = relationship("Content", back_populates="project", cascade="all, delete-orphan")
    plannings = relationship("Planning", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="project", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    workflow_tasks = relationship("WorkflowTask", back_populates="project", cascade="all, delete-orphan")


class Content(Base, BaseModel):
    __tablename__ = "contents"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    title = Column(String(500))
    summary = Column(Text)
    audience = Column(String(200))
    emotion = Column(String(100))
    tags = Column(JSON, nullable=True)
    score = Column(DECIMAL(5, 2), nullable=True)

    project = relationship("ContentProject", back_populates="contents")


class Planning(Base, BaseModel):
    __tablename__ = "plannings"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    target = Column(String(200))
    style = Column(String(100))
    duration = Column(Integer)
    scene = Column(String(200))
    strategy = Column(Text)

    project = relationship("ContentProject", back_populates="plannings")


class Script(Base, BaseModel):
    __tablename__ = "scripts"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    type = Column(String(50), index=True)
    content = Column(Text)
    version = Column(Integer, default=1)
    score = Column(DECIMAL(5, 2), nullable=True)

    project = relationship("ContentProject", back_populates="scripts")


class Review(Base, BaseModel):
    __tablename__ = "reviews"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    original_score = Column(DECIMAL(5, 2), nullable=True)
    marketing_score = Column(DECIMAL(5, 2), nullable=True)
    risk_score = Column(DECIMAL(5, 2), nullable=True)
    consult_score = Column(DECIMAL(5, 2), nullable=True)
    result = Column(String(50))

    project = relationship("ContentProject", back_populates="reviews")


class Video(Base, BaseModel):
    __tablename__ = "videos"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    script_id = Column(Integer, nullable=True)
    url = Column(String(500))
    cover_url = Column(String(500))
    duration = Column(Integer)
    resolution = Column(String(50))
    status = Column(String(50), default="generating", index=True)

    project = relationship("ContentProject", back_populates="videos")


class WorkflowTask(Base, BaseModel):
    __tablename__ = "workflow_tasks"

    project_id = Column(Integer, ForeignKey("content_projects.id"), index=True, nullable=False)
    task_type = Column(String(50), index=True)
    status = Column(String(50), default="waiting", index=True)
    progress = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    project = relationship("ContentProject", back_populates="workflow_tasks")


class UserMemory(Base, BaseModel):
    __tablename__ = "user_memory"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    memory_type = Column(String(50), index=True)
    content = Column(Text)
    weight = Column(DECIMAL(5, 4), default=0.5)

    user = relationship("User", back_populates="memory")
