"""
四大审核 Agent - AI内容质量控制中心

大健康领域内容需要特殊审核：
1. 健康合规 - 确保不涉及医疗建议、不夸大效果
2. 营销自然度 - 确保内容不像硬广告，保持咨询属性
3. 爆款质量 - 检查开头、节奏、情绪、互动设计
4. 咨询转化 - 检查是否引导私信咨询，而非直接销售
"""

from typing import Dict, Any, List, Tuple
import re


class HealthComplianceAgent:
    """
    健康合规专家

    检查内容是否涉及违规医疗表述：
    - 治疗疾病（需要改为改善生活方式）
    - 夸大效果
    - 绝对化用语
    """

    # 禁止词列表（高风险）
    FORBID_KEYWORDS = [
        "治疗", "治愈", "根治", "药到病除",
        "降血糖", "降血压", "抗癌", "防癌",
        "处方药", "特效药", "速效",
        "百分百", "保证", "一定有效",
        "医生推荐", "专家推荐", "医院使用",
    ]

    # 警告词列表（中风险）
    WARN_KEYWORDS = [
        "疗效", "药效", "药理",
        "康复", "痊愈", "根除",
        "立竿见影", "马上见效", "几天就好",
        "临床验证", "医学认证",
    ]

    # 建议替换词
    SUGGEST_REPLACEMENTS = {
        "治疗糖尿病": "帮助改善血糖管理",
        "治疗高血压": "帮助血压管理",
        "治疗失眠": "改善睡眠质量",
        "降血糖": "帮助稳定血糖",
        "降血压": "帮助血压平稳",
        "治愈": "改善",
        "根治": "调理",
        "保证有效": "可能帮助",
        "立竿见影": "坚持可见效果",
    }

    def analyze(self, content: str) -> Dict[str, Any]:
        """分析内容健康合规性"""
        issues = []
        warnings = []
        suggestions = []

        # 检查禁止词
        for keyword in self.FORBID_KEYWORDS:
            if keyword in content:
                issues.append(f"包含高风险词汇：{keyword}")
                # 提供替换建议
                for old, new in self.SUGGEST_REPLACEMENTS.items():
                    if old in content and keyword in old:
                        suggestions.append(f"建议将「{old}」改为「{new}」")

        # 检查警告词
        for keyword in self.WARN_KEYWORDS:
            if keyword in content and keyword not in [i.split("：")[-1] for i in issues]:
                warnings.append(f"包含敏感词汇：{keyword}")

        # 计算评分
        score = 100
        score -= len(issues) * 20  # 每个高风险词扣20分
        score -= len(warnings) * 10  # 每个警告词扣10分
        score = max(0, score)

        # 确定风险等级
        if len(issues) > 0:
            risk_level = "high"
        elif len(warnings) > 0:
            risk_level = "medium"
        else:
            risk_level = "safe"

        return {
            "score": score,
            "risk_level": risk_level,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "summary": "内容健康合规" if score >= 90 else f"发现{len(issues)}个高风险问题，{len(warnings)}个警告",
        }


class MarketingRiskAgent:
    """
    营销风险专家

    检查内容是否像硬广告：
    - 强销售用语
    - 价格引导
    - 购买链接
    - 过度产品暗示
    """

    # 硬广词汇
    HARD_SELL_KEYWORDS = [
        "购买", "下单", "抢购", "限时优惠",
        "原价", "现价", "秒杀", "团购",
        "点击购买", "立即购买", "扫码购买",
        "找我买", "私信买", "微信转账",
        "库存有限", "售完即止", "错过不再",
    ]

    # 软广词汇（需注意）
    SOFT_SELL_KEYWORDS = [
        "推荐", "建议使用", "我家产品",
        "同款", "私信我", "评论区",
        "链接在", "主页有",
    ]

    # 咨询引导词（推荐）
    CONSULT_KEYWORDS = [
        "可以留言", "欢迎交流", "一起讨论",
        "私信咨询", "评论区见", "有问题可以问我",
    ]

    def analyze(self, content: str) -> Dict[str, Any]:
        """分析营销自然度"""
        hard_sells = []
        soft_sells = []

        # 检查硬广词
        for keyword in self.HARD_SELL_KEYWORDS:
            if keyword in content:
                hard_sells.append(keyword)

        # 检查软广词
        for keyword in self.SOFT_SELL_KEYWORDS:
            if keyword in content:
                soft_sells.append(keyword)

        # 检查咨询引导
        has_consult = any(keyword in content for keyword in self.CONSULT_KEYWORDS)

        # 计算评分
        score = 100
        score -= len(hard_sells) * 25  # 硬广词扣25分
        score -= len(soft_sells) * 10  # 软广词扣10分
        if has_consult:
            score += 10  # 有咨询引导加10分
        score = min(100, max(0, score))

        # 确定风险等级
        if len(hard_sells) > 0:
            risk_level = "high"
        elif len(soft_sells) > 2:
            risk_level = "medium"
        else:
            risk_level = "safe"

        suggestions = []
        if hard_sells:
            suggestions.append("建议移除硬广词汇，改为自然引导")
        if not has_consult:
            suggestions.append("建议增加自然咨询引导，如「有问题可以留言交流」")

        return {
            "score": score,
            "risk_level": risk_level,
            "hard_sells": hard_sells,
            "soft_sells": soft_sells,
            "has_consult_guide": has_consult,
            "suggestions": suggestions,
            "summary": "营销自然度良好" if score >= 85 else f"发现{len(hard_sells)}处硬广，建议优化",
        }


class ViralQualityAgent:
    """
    爆款质量专家

    检查内容是否具备爆款潜质：
    - 开头3秒是否抓人
    - 情绪节奏是否流畅
    - 是否有互动设计
    - 是否有认知反转
    """

    # 有效开头模式
    GOOD_OPENINGS = [
        r"为什么.{1,10}却",
        r"很多人不知道",
        r"大家都在犯的错误",
        r"真相是",
        r"你有没有发现",
        r"很多人以为",
        r"别再.{1,5}了",
    ]

    # 高潮模式
    CLIMAX_PATTERNS = [
        "其实", "真正的", "关键在于", "核心是",
        "所以", "这就是为什么", "原来",
    ]

    # 互动引导
    INTERACTION_PATTERNS = [
        "你怎么看", "你怎么想", "你同意吗",
        "评论区", "留言", "点赞", "关注",
        "转发给", "收藏", "分享",
    ]

    def analyze(self, content: str) -> Dict[str, Any]:
        """分析爆款质量"""
        opening_score = 0
        climax_score = 0
        interaction_score = 0

        issues = []
        suggestions = []

        # 检查开头质量
        first_sentence = content.split("。")[0] if "。" in content else content[:50]
        for pattern in self.GOOD_OPENINGS:
            if re.search(pattern, first_sentence):
                opening_score = 30
                break

        if opening_score == 0:
            issues.append("开头缺乏吸引力")
            suggestions.append("建议开头制造疑问或反常识")

        # 检查高潮设计
        for pattern in self.CLIMAX_PATTERNS:
            if pattern in content:
                climax_score = 25
                break

        if climax_score == 0:
            suggestions.append("建议增加认知反转或高潮点")

        # 检查互动引导
        for pattern in self.INTERACTION_PATTERNS:
            if pattern in content:
                interaction_score = 25
                break

        if interaction_score == 0:
            issues.append("缺少互动引导")
            suggestions.append("建议结尾增加「你怎么看」等互动引导")

        # 检查节奏（长度适中）
        content_length = len(content)
        if content_length < 100:
            issues.append("内容过短")
            suggestions.append("建议增加案例或解释，内容长度建议200-500字")
        elif content_length > 800:
            suggestions.append("内容较长，建议精简或分段")

        # 综合评分
        length_score = 20 if 200 <= content_length <= 600 else 10
        score = opening_score + climax_score + interaction_score + length_score

        return {
            "score": score,
            "opening_score": opening_score,
            "climax_score": climax_score,
            "interaction_score": interaction_score,
            "length_score": length_score,
            "content_length": content_length,
            "issues": issues,
            "suggestions": suggestions,
            "summary": "爆款质量优秀" if score >= 85 else f"开头{opening_score}分，建议优化",
        }


class ConversionAgent:
    """
    咨询转化专家

    检查内容是否自然引导咨询：
    - 是否有私信入口
    - 是否避免直接销售
    - 是否建立信任感
    """

    # 信任建立词
    TRUST_PATTERNS = [
        "很多粉丝问我", "最近很多人问",
        "我自己试过", "身边朋友",
        "很多学员", "很多用户",
    ]

    # 自然咨询引导
    NATURAL_GUIDES = [
        "如果你也有类似困扰",
        "想知道更多可以",
        "有问题欢迎",
        "需要建议可以",
        "具体情况因人而异",
        "建议咨询专业人士",
    ]

    # 直接销售词（避免）
    DIRECT_SALES = [
        "加我微信", "私信购买", "点击下单",
        "立即购买", "限时优惠", "现在下单",
    ]

    def analyze(self, content: str) -> Dict[str, Any]:
        """分析咨询转化潜力"""
        trust_score = 0
        guide_score = 0
        sales_penalty = 0

        suggestions = []

        # 检查信任建立
        for pattern in self.TRUST_PATTERNS:
            if pattern in content:
                trust_score = 30
                break

        if trust_score == 0:
            suggestions.append("建议增加信任感建立，如「最近很多粉丝问我...」")

        # 检查自然咨询引导
        for pattern in self.NATURAL_GUIDES:
            if pattern in content:
                guide_score = 40
                break

        if guide_score == 0:
            suggestions.append("建议增加自然咨询引导，如「如果你也有类似困扰，可以留言交流」")

        # 检查直接销售词（扣分）
        for pattern in self.DIRECT_SALES:
            if pattern in content:
                sales_penalty = 30
                suggestions.append(f"建议移除「{pattern}」，改为自然引导")
                break

        # 综合评分
        base_score = 30  # 基础分
        score = base_score + trust_score + guide_score - sales_penalty
        score = min(100, max(0, score))

        return {
            "score": score,
            "trust_score": trust_score,
            "guide_score": guide_score,
            "has_direct_sales": sales_penalty > 0,
            "suggestions": suggestions,
            "summary": "转化潜力良好" if score >= 80 else "建议优化咨询引导",
        }