# ==============================================================================
# Copyright (C) 2021 Evil0ctal
#
# This file is part of the Douyin_TikTok_Download_API project.
#
# This project is licensed under the Apache License 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
#
# WeChat Channels (视频号) video crawler
# 微信视频号视频地址解析爬虫
#
# Notes:
# - Channels share links redirect to a Vue SPA preview page at
#   https://channels.weixin.qq.com/finder-preview/pages/sph?id=<id>
# - A POST API is used to fetch feed metadata:
#   POST https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info
#   Body: {"baseReq":{"generalToken":""},"shortUri":"<id>"}
# - The API returns metadata (title, author, cover, stats) but the actual
#   video stream URL is not exposed and requires the WeChat client to play.
#
# ==============================================================================

import asyncio
import json
import os
import re
import time

import httpx
import yaml

from crawlers.base_crawler import BaseCrawler

# Config file path
path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

with open(f"{path}/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class WeChatChannelsCrawler:
    """
    微信视频号视频爬虫 (WeChat Channels video crawler)
    """

    async def get_wechat_channels_headers(self):
        """Read request headers from config file"""
        ch_config = config["TokenManager"]["wechat"]["channels"]
        return {
            "headers": {
                "User-Agent": ch_config["headers"]["User-Agent"],
                "Referer": ch_config["headers"]["Referer"],
                "Accept-Language": ch_config["headers"]["Accept-Language"],
                "Cookie": ch_config["headers"].get("Cookie", "") or "",
            },
            "proxies": {
                "http://": ch_config["proxies"]["http"],
                "https://": ch_config["proxies"]["https"],
            },
        }

    "-------------------------------------------------------utils-------------------------------------------------------"

    @staticmethod
    def _extract_id(url: str) -> str:
        """
        Extract the short ID from a Channels share URL.

        Supported formats:
        - https://weixin.qq.com/sph/AephiOqocB
        - https://channels.weixin.qq.com/finder-preview/pages/sph?id=AephiOqocB
        """
        # Try /sph/ID pattern
        match = re.search(r"/sph/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        # Try id= query param
        match = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        return url.strip("/").split("/")[-1]

    @staticmethod
    def _timestamp_to_str(ts: int) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except (ValueError, OSError):
            return None

    "-------------------------------------------------------handler-------------------------------------------------------"

    async def resolve_share_url(self, url: str) -> str:
        """
        Resolve a Channels short link by following redirects.
        """
        if any(host in url for host in ("weixin.qq.com/sph", "w.url.cn", "t.cn")):
            kwargs = await self.get_wechat_channels_headers()
            async with httpx.AsyncClient(
                headers=kwargs["headers"],
                follow_redirects=True,
                timeout=10
            ) as client:
                response = await client.get(url)
                return str(response.url)
        return url

    async def fetch_video(self, url: str) -> dict:
        """
        Parse a single WeChat Channels video address via the official feed API.

        :param url: Channels share link (weixin.qq.com/sph/... or channels.weixin.qq.com/...)
        :return: Structured video data (title/nickname/cover/description/stats)
        """
        # Resolve short link first
        real_url = await self.resolve_share_url(url)
        short_id = self._extract_id(real_url)

        if not short_id:
            raise ValueError(f"Could not extract short ID from URL: {url}")

        kwargs = await self.get_wechat_channels_headers()

        # Build API request headers
        api_headers = {
            **kwargs["headers"],
            "Origin": "https://channels.weixin.qq.com",
            "Content-Type": "application/json",
            "Referer": f"https://channels.weixin.qq.com/finder-preview/pages/sph?id={short_id}",
        }

        api_url = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
        api_body = {
            "baseReq": {"generalToken": ""},
            "shortUri": short_id,
        }

        async with httpx.AsyncClient(
            headers=api_headers,
            proxies=kwargs["proxies"],
            timeout=15
        ) as client:
            response = await client.post(api_url, json=api_body)

        if response.status_code != 201:
            raise ValueError(
                f"WeChat Channels API returned status {response.status_code}. "
                f"The video may require opening in the WeChat client."
            )

        result = response.json()
        if result.get("errCode") != 0:
            err_msg = result.get("errMsg", {}).get("message", "Unknown error")
            raise ValueError(
                f"WeChat Channels API error: {err_msg} (errCode={result.get('errCode')})"
            )

        feed_data = result.get("data", {})
        feed_info = feed_data.get("feedInfo", {})
        author_info = feed_data.get("authorInfo", {})

        # Parse createtime
        create_ts = feed_info.get("createtime")
        publish_time = self._timestamp_to_str(create_ts) if create_ts else None

        return {
            "url": real_url,
            "short_id": short_id,
            "title": feed_info.get("description"),
            "nickname": author_info.get("nickname"),
            "author_avatar": author_info.get("headImgUrl"),
            "cover_url": feed_info.get("coverUrl"),
            "description": feed_info.get("description"),
            "publish_timestamp": create_ts,
            "publish_time": publish_time,
            "like_count": feed_info.get("likeCountFmt"),
            "favorite_count": feed_info.get("favCountFmt"),
            "forward_count": feed_info.get("forwardCountFmt"),
            "comment_count": feed_info.get("commentCountFmt"),
            "dynamic_export_id": feed_data.get("sceneInfo", {}).get("dynamicExportId"),
            "video_url": None,  # Video URL is not exposed by the API
            "note": "Video stream URL is not available via public API. "
                    "Playback requires the WeChat client app.",
            "raw_feed_info": feed_info,
            "raw_author_info": author_info,
        }

    async def fetch_page_html(self, url: str) -> str:
        """
        Fetch the Channels share page raw HTML (for debugging/custom parsing).
        Note: The modern preview page is a Vue SPA and no longer contains
        embedded JSON feed data. Use fetch_video() which calls the API instead.
        """
        kwargs = await self.get_wechat_channels_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            response = await crawler.fetch_response(url)
            return response.text

    async def update_cookie(self, cookie: str):
        """Update Channels request cookie"""
        global config
        config["TokenManager"]["wechat"]["channels"]["headers"]["Cookie"] = cookie
        config_path = f"{path}/config.yaml"
        with open(config_path, "w", encoding="utf-8") as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)

    "-------------------------------------------------------main-------------------------------------------------------"

    async def main(self):
        url = "https://weixin.qq.com/sph/AephiOqocB"
        result = await self.fetch_video(url)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    crawler = WeChatChannelsCrawler()
    start = time.time()
    asyncio.run(crawler.main())
    end = time.time()
    print(f"耗时: {end - start:.2f}s")
