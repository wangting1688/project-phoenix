# -*- coding: utf-8 -*-
"""抖音链接解析与视频抓取（尽力而为，不依赖第三方服务）。

抖音反爬会变，这里只做「能拿到就用、拿不到不编造」：
- resolve_video_id: 短链重定向 + 长链正则提取 aweme_id
- fetch_video_meta: 尝试无 cookie 详情接口取标题/时长/封面
- download_video: 尝试从详情接口取直链下载视频

可配置 DOUYIN_COOKIE 提升成功率；没有 cookie 时失败会返回空，不阻塞分析。
"""
import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)
TIMEOUT = 20
_ITEMINFO_URL = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"


def _headers() -> Dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.douyin.com/",
        "Accept": "application/json, text/plain, */*",
    }
    cookie = os.environ.get("DOUYIN_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    return headers


def resolve_video_id(url: str) -> Optional[str]:
    """从抖音链接提取 aweme_id；支持长链和 v.douyin.com 短链。"""
    if not url:
        return None
    # 用户常直接粘贴「复制打开抖音...https://v.douyin.com/xxx/...」整段口令，
    # 先从文本里抽出 URL 再解析。
    m = re.search(r"https?://[^\s]+", url)
    if m:
        url = m.group(0)
    m = re.search(r"/video/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"video_id=(\d+)", url)
    if m:
        return m.group(1)
    if "v.douyin.com" not in url:
        return None
    try:
        r = requests.get(
            url, headers={"User-Agent": UA}, allow_redirects=True, timeout=TIMEOUT
        )
        m = re.search(r"/video/(\d+)", r.url)
        if m:
            return m.group(1)
    except Exception as e:
        logger.warning("抖音短链解析失败: %s", e)
    return None


def fetch_video_meta(video_id: str) -> Dict[str, Any]:
    """尝试获取标题/时长/封面。失败时返回空字段，不抛异常。"""
    meta: Dict[str, Any] = {
        "video_id": video_id,
        "title": "",
        "duration": None,
        "cover_url": "",
    }
    try:
        r = requests.get(
            _ITEMINFO_URL,
            params={"item_ids": video_id},
            headers=_headers(),
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return meta
        data = r.json()
        item = (data.get("item_list") or [{}])[0]
        meta["title"] = (item.get("desc") or "").strip()
        video = item.get("video") or {}
        dur = video.get("duration")
        if dur:
            meta["duration"] = int(dur) // 1000
        covers = (video.get("cover") or {}).get("url_list") or []
        if covers:
            meta["cover_url"] = covers[0]
    except Exception as e:
        logger.warning("抖音元数据抓取失败: %s", e)

    # 老接口失效时，退回视频页 HTML 解析（RENDER_DATA / description）
    if not meta.get("title"):
        try:
            r = requests.get(
                f"https://www.douyin.com/video/{video_id}",
                headers=_headers(),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                html = r.text
                _extract_meta_from_html(html, meta)
        except Exception as e:
            logger.warning("抖音视频页解析失败: %s", e)
    return meta


def _extract_meta_from_html(html: str, meta: Dict[str, Any]) -> None:
    """从视频页 HTML 提取标题/封面/时长（尽力而为）。"""
    # RENDER_DATA 是 URL 编码 JSON
    m = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if m:
        try:
            import json as _json
            data = _json.loads(m.group(1))
            loader = data.get("loaderData") or {}
            for k, v in loader.items():
                if not isinstance(v, dict):
                    continue
                video_info = (
                    (v.get("videoInfoRes") or {}).get("item_list") or
                    (v.get("awemeDetail") or {}).get("item_list") or
                    []
                )
                if video_info:
                    item = video_info[0]
                    if not meta.get("title"):
                        meta["title"] = str(item.get("desc") or "").strip()
                    video = item.get("video") or {}
                    if meta.get("duration") is None and video.get("duration"):
                        meta["duration"] = int(video["duration"]) // 1000
                    covers = (video.get("cover") or {}).get("url_list") or []
                    if not meta.get("cover_url") and covers:
                        meta["cover_url"] = covers[0]
        except Exception:
            pass
    if not meta.get("title"):
        m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if m:
            meta["title"] = m.group(1).strip()


def download_video(video_id: str, out_path: Path) -> bool:
    """尝试下载抖音视频到 out_path，成功返回 True。"""
    try:
        r = requests.get(
            _ITEMINFO_URL,
            params={"item_ids": video_id},
            headers=_headers(),
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        item = (data.get("item_list") or [{}])[0]
        video = item.get("video") or {}
        play = (video.get("play_addr") or {}).get("url_list") or []
        if not play:
            return False
        r2 = requests.get(
            play[0], headers={"User-Agent": UA}, stream=True, timeout=60
        )
        if r2.status_code != 200:
            return False
        with open(out_path, "wb") as f:
            for chunk in r2.iter_content(65536):
                f.write(chunk)
        return out_path.stat().st_size > 1024
    except Exception as e:
        logger.warning("抖音视频下载失败: %s", e)

    # 老接口失效时，从视频页 HTML 提取播放地址再下载
    try:
        r = requests.get(
            f"https://www.douyin.com/video/{video_id}",
            headers=_headers(),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            html = r.text
            m = re.search(r'"playAddr"\s*:\s*"([^"]+)"', html) or \
                re.search(r'"play_addr"\s*:\s*"([^"]+)"', html)
            if m:
                play_url = m.group(1).replace("\\u002F", "/").replace("\\/", "/")
                r2 = requests.get(
                    play_url, headers={"User-Agent": UA}, stream=True, timeout=60
                )
                if r2.status_code == 200:
                    with open(out_path, "wb") as f:
                        for chunk in r2.iter_content(65536):
                            f.write(chunk)
                    return out_path.stat().st_size > 1024
    except Exception as e:
        logger.warning("抖音视频页下载失败: %s", e)
    return False
