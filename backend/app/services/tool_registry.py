"""
Agent工具注册框架

TASK-016.3B.1: AI Agent Tool Gateway

提供工具注册、发现、调用的统一框架，使Agent能够灵活调用各种外部AI能力。
"""

from typing import Dict, Any, Callable, Optional, List, Type
from dataclasses import dataclass, field
from enum import Enum
import json


class ToolCategory(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"
    MEDIA = "media"
    AI = "ai"
    UTILITY = "utility"


class ToolStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    LOADING = "loading"
    ERROR = "error"


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolSchema:
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter] = field(default_factory=list)
    returns: str = "json"
    version: str = "1.0"
    status: ToolStatus = ToolStatus.UNAVAILABLE
    provider: str = "unknown"
    cost: float = 0.0
    rate_limit: int = 100


class ToolRegistry:
    """工具注册中心"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, dict] = {}
        return cls._instance

    def register(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        func: Callable,
        parameters: List[ToolParameter],
        returns: str = "json",
        version: str = "1.0",
        provider: str = "unknown",
        cost: float = 0.0,
        rate_limit: int = 100,
    ):
        """注册工具"""
        self._tools[name] = {
            "schema": ToolSchema(
                name=name,
                description=description,
                category=category,
                parameters=parameters,
                returns=returns,
                version=version,
                status=ToolStatus.AVAILABLE,
                provider=provider,
                cost=cost,
                rate_limit=rate_limit,
            ),
            "func": func,
        }

    def unregister(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]

    def get_tool(self, name: str) -> Optional[dict]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[ToolSchema]:
        """列出工具"""
        schemas = [tool["schema"] for tool in self._tools.values()]
        if category:
            schemas = [s for s in schemas if s.category == category]
        return schemas

    def find_by_category(self, category: ToolCategory) -> List[ToolSchema]:
        """按类别查找工具"""
        return self.list_tools(category)

    def get_llm_tool_list(self) -> List[dict]:
        """获取适合LLM调用的工具列表格式"""
        tools = []
        for tool in self._tools.values():
            schema = tool["schema"]
            if schema.status != ToolStatus.AVAILABLE:
                continue

            params = {}
            for param in schema.parameters:
                params[param.name] = {
                    "type": param.type,
                    "description": param.description,
                    "required": param.required,
                }

            tools.append({
                "name": schema.name,
                "description": schema.description,
                "parameters": params,
            })

        return tools

    def call_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """调用工具"""
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found"}

        schema = tool["schema"]
        if schema.status != ToolStatus.AVAILABLE:
            return {"success": False, "error": f"Tool '{name}' is not available"}

        func = tool["func"]
        try:
            result = func(**kwargs)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


class BaseTool:
    """工具基类"""

    NAME: str = ""
    DESCRIPTION: str = ""
    CATEGORY: ToolCategory = ToolCategory.UTILITY
    PARAMETERS: List[ToolParameter] = []
    RETURNS: str = "json"
    VERSION: str = "1.0"
    PROVIDER: str = "unknown"
    COST: float = 0.0
    RATE_LIMIT: int = 100

    def __init__(self):
        self._registry = ToolRegistry()

    def register(self):
        """注册工具到注册表"""
        self._registry.register(
            name=self.NAME,
            description=self.DESCRIPTION,
            category=self.CATEGORY,
            func=self.execute,
            parameters=self.PARAMETERS,
            returns=self.RETURNS,
            version=self.VERSION,
            provider=self.PROVIDER,
            cost=self.COST,
            rate_limit=self.RATE_LIMIT,
        )

    def execute(self, **kwargs) -> Any:
        """执行工具（子类实现）"""
        raise NotImplementedError

    def get_schema(self) -> ToolSchema:
        """获取工具schema"""
        return ToolSchema(
            name=self.NAME,
            description=self.DESCRIPTION,
            category=self.CATEGORY,
            parameters=self.PARAMETERS,
            returns=self.RETURNS,
            version=self.VERSION,
            provider=self.PROVIDER,
            cost=self.COST,
            rate_limit=self.RATE_LIMIT,
        )


class ToolCallResult:
    """工具调用结果"""

    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }

    @classmethod
    def success(cls, data: Any) -> "ToolCallResult":
        return cls(success=True, data=data)

    @classmethod
    def error(cls, error: str) -> "ToolCallResult":
        return cls(success=False, error=error)
