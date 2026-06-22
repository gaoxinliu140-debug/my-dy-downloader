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
# WeChat Official Account (公众号) article crawler
# 微信公众号文章解析爬虫
#
# 说明 / Notes:
# - 公众号文章页面 (mp.weixin.qq.com/s) 为公开可访问的静态 HTML 页面，
#   本爬虫通过抓取文章 HTML 并解析其中的元数据 (标题/作者/正文/图片/视频) 实现解析。
# - The article page on mp.weixin.qq.com/s is a publicly accessible static HTML page.
#   This crawler fetches the article HTML and parses metadata (title/author/content/images/video).
#
# ==============================================================================

import asyncio
import html
import os
import re
import time

import yaml

import aiofiles
import html2text
import httpx

from crawlers.base_crawler import BaseCrawler
from crawlers.utils.api_exceptions import APINotFoundError, APIResponseError

# 配置文件路径 / Config file path
path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

with open(f"{path}/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class WeChatMpCrawler:
    """
    微信公众号文章爬虫 (WeChat Official Account article crawler)
    """

    # 从配置文件读取请求头 / Read request headers from config file
    async def get_wechat_mp_headers(self):
        mp_config = config["TokenManager"]["wechat"]["mp"]
        kwargs = {
            "headers": {
                "User-Agent": mp_config["headers"]["User-Agent"],
                "Referer": mp_config["headers"]["Referer"],
                "Accept-Language": mp_config["headers"]["Accept-Language"],
                "Cookie": mp_config["headers"].get("Cookie", "") or "",
            },
            "proxies": {
                "http://": mp_config["proxies"]["http"],
                "https://": mp_config["proxies"]["https"],
            },
        }
        return kwargs

    "-------------------------------------------------------utils-------------------------------------------------------"

    @staticmethod
    def get_article_id(url: str) -> dict:
        """
        从公众号文章 URL 中提取标识参数 (biz/mid/idx/sn)
        Extract identifiers (biz/mid/idx/sn) from the article URL.
        """
        identifiers = {}
        for key in ("__biz", "mid", "idx", "sn"):
            match = re.search(rf"[?&]{re.escape(key)}=([^&#]+)", url)
            if match:
                identifiers[key.strip("_")] = match.group(1)
        return identifiers

    @staticmethod
    def _search(pattern: str, text: str, group: int = 1):
        match = re.search(pattern, text, re.S)
        if match:
            return html.unescape(match.group(group)).strip()
        return None

    @staticmethod
    def _clean_html(raw: str) -> str:
        """去除 HTML 标签，提取纯文本 / Strip HTML tags into plain text."""
        if not raw:
            return ""
        # 移除 script/style 块
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
        # 换行类标签转为换行符
        raw = re.sub(r"<(br|/p|/div|/section|/h[1-6])[^>]*>", "\n", raw, flags=re.I)
        # 移除其余标签
        raw = re.sub(r"<[^>]+>", "", raw)
        raw = html.unescape(raw)
        # 折叠多余空行
        raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
        return raw.strip()

    "-------------------------------------------------------handler-------------------------------------------------------"

    async def fetch_article_html(self, url: str) -> str:
        """
        获取公众号文章原始 HTML (Fetch raw article HTML)
        """
        kwargs = await self.get_wechat_mp_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            response = await crawler.fetch_response(url)
            return response.text

    async def fetch_article(self, url: str) -> dict:
        """
        解析单篇公众号文章 (Parse a single WeChat official account article)

        :param url: 公众号文章链接 (https://mp.weixin.qq.com/s/...)
        :return: 文章结构化数据 (title/author/account/publish_time/content/images/video_urls)
        """
        if "mp.weixin.qq.com" not in url:
            raise APIResponseError("Invalid WeChat MP article URL: must contain mp.weixin.qq.com")

        raw = await self.fetch_article_html(url)

        # 文章被删除 / 需要验证 的提示页面
        if "操作频繁" in raw or "环境异常" in raw:
            raise APIResponseError("WeChat MP access blocked (environment abnormal / rate limited). Provide a valid Cookie in config.yaml.")
        if "该内容已被发布者删除" in raw or "此内容因违规无法查看" in raw or "该内容已被" in raw:
            raise APINotFoundError("WeChat MP article has been deleted or is unavailable.")

        # 标题 / Title
        title = (
            self._search(r'var\s+msg_title\s*=\s*[\'"](.+?)[\'"]', raw)
            or self._search(r'<meta\s+property="og:title"\s+content="(.+?)"', raw)
            or self._search(r'id="activity-name"[^>]*>(.*?)</h1>', raw)
            or self._search(r"<title>(.*?)</title>", raw)
        )

        # 作者 / Author
        author = (
            self._search(r'var\s+author\s*=\s*[\'"](.*?)[\'"]', raw)
            or self._search(r'id="js_author_name"[^>]*>(.*?)</', raw)
            or self._search(r'<meta\s+name="author"\s+content="(.*?)"', raw)
        )

        # 公众号名称 / Account name
        account = (
            self._search(r'var\s+nickname\s*=\s*[\'"](.*?)[\'"]', raw)
            or self._search(r'id="js_name"[^>]*>(.*?)</', raw)
        )

        # 发布时间 / Publish time
        publish_timestamp = self._search(r'var\s+ct\s*=\s*[\'"](\d+)[\'"]', raw)
        publish_time = None
        if publish_timestamp:
            try:
                publish_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(publish_timestamp)))
            except (ValueError, OSError):
                publish_time = None

        # 摘要 / Digest
        digest = (
            self._search(r'var\s+msg_desc\s*=\s*[\'"](.*?)[\'"]', raw)
            or self._search(r'<meta\s+property="og:description"\s+content="(.*?)"', raw)
            or self._search(r'<meta\s+name="description"\s+content="(.*?)"', raw)
        )

        # 封面 / Cover
        cover = (
            self._search(r'var\s+msg_cdn_url\s*=\s*[\'"](.*?)[\'"]', raw)
            or self._search(r'<meta\s+property="og:image"\s+content="(.*?)"', raw)
        )

        # 正文 HTML / Content HTML
        content_html = self._search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', raw)
        if not content_html:
            content_html = self._search(r'id="js_content"[^>]*>(.*)', raw)

        # 正文图片 / Content images
        images = []
        if content_html:
            for img_match in re.finditer(r'data-src="([^"]+)"|<img[^>]+src="([^"]+)"', content_html):
                src = img_match.group(1) or img_match.group(2)
                if src and src.startswith("http") and src not in images:
                    images.append(src)

        # 正文纯文本 / Plain text content
        content_text = self._clean_html(content_html) if content_html else None

        # 内嵌视频 / Embedded videos (mp_video / 腾讯视频 vid)
        video_urls = []
        for vid_match in re.finditer(r'data-mpvid="([^"]+)"|mpvideo\?vid=([^"&]+)', raw):
            vid = vid_match.group(1) or vid_match.group(2)
            if vid and vid not in video_urls:
                video_urls.append(vid)
        tencent_vids = re.findall(r'data-src="https://v\.qq\.com[^"]*vid=([^"&]+)"', raw)
        for vid in tencent_vids:
            if vid not in video_urls:
                video_urls.append(vid)

        data = {
            "url": url,
            "identifiers": self.get_article_id(url),
            "title": title,
            "author": author,
            "account": account,
            "publish_timestamp": int(publish_timestamp) if publish_timestamp else None,
            "publish_time": publish_time,
            "digest": digest,
            "cover": cover,
            "images": images,
            "video_vids": video_urls,
            "content_text": content_text,
            "content_html": content_html,
        }
        return data

    async def update_cookie(self, cookie: str):
        """更新公众号请求 Cookie / Update WeChat MP request cookie."""
        global config
        config["TokenManager"]["wechat"]["mp"]["headers"]["Cookie"] = cookie
        config_path = f"{path}/config.yaml"
        with open(config_path, "w", encoding="utf-8") as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)


    "----------------------------------------------download---------------------------------------------------"

    async def download_article(self, url: str, output_dir: str = None) -> dict:
        """
        Fetch a WeChat MP article, download images locally, and save as HTML + Markdown.

        :param url: Article URL
        :param output_dir: Output directory (default: './downloads/wechat_mp/')
        :return: Dict with saved file paths and article metadata
        """
        import json
        import os
        import re

        article = await self.fetch_article(url)
        if not article.get('title'):
            title = 'untitled'
        else:
            title = re.sub(r'[\\/:*?"<>|]', '_', article['title'])[:80]

        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), 'downloads', 'wechat_mp')

        article_dir = os.path.join(output_dir, title)
        images_dir = article_dir
        os.makedirs(images_dir, exist_ok=True)

        kwargs = await self.get_wechat_mp_headers()
        download_headers = {
            **kwargs['headers'],
            'Referer': 'https://mp.weixin.qq.com/',
        }

        image_map = {}
        downloaded_images = []

        for i, img_url in enumerate(article.get('images', [])):
            ext = '.jpg'
            ext_match = re.search(r'wx_fmt=(\w+)', img_url)
            if ext_match:
                ext = '.' + ext_match.group(1)
            filename = f'image_{i:03d}{ext}'
            filepath = os.path.join(images_dir, filename)
            try:
                async with httpx.AsyncClient(
                    headers=download_headers,
                    proxies=kwargs['proxies'],
                    timeout=30,
                    follow_redirects=True
                ) as client:
                    resp = await client.get(img_url)
                    if resp.status_code == 200:
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(resp.content)
                        image_map[img_url] = filename
                        downloaded_images.append({
                            'original_url': img_url,
                            'local_path': filename,
                            'full_path': filepath,
                        })
            except Exception as e:
                print(f'Failed to download image {img_url}: {e}')

        html_content = article.get('content_html', '') or ''
        if html_content:
            for original_url, local_path in image_map.items():
                local_path_escaped = local_path.replace('\\', '/')
                html_content = html_content.replace(f'data-src="{original_url}"', f'src="{local_path_escaped}"')
                html_content = html_content.replace(f'src="{original_url}"', f'src="{local_path_escaped}"')

        # Build full HTML
        safe_title = (article.get('title', '') or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_author = (article.get('author', '') or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_account = (article.get('account', '') or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_time = (article.get('publish_time', '') or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.8; color: #333; }}
h1 {{ font-size: 1.5em; margin-bottom: 0.5em; }}
.article-meta {{ color: #888; font-size: 0.9em; margin-bottom: 2em; }}
.article-meta span {{ margin-right: 1em; }}
img {{ max-width: 100%; height: auto; display: block; margin: 1em auto; border-radius: 8px; }}
section {{ overflow-wrap: break-word; }}
</style>
</head>
<body>
<h1>{safe_title}</h1>
<div class="article-meta">
<span>作者: {safe_author}</span>
<span>公众号: {safe_account}</span>
<span>发布时间: {safe_time}</span>
</div>
<section>
{html_content}
</section>
</body>
</html>"""

        html_path = os.path.join(article_dir, 'article.html')
        async with aiofiles.open(html_path, 'w', encoding='utf-8') as f:
            await f.write(full_html)

        md_body = ''
        if html_content:
            h = html2text.HTML2Text()
            h.body_width = 0
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.skip_internal_links = False
            h.protect_links = True
            h.unicode_snob = True
            md_body = h.handle(html_content)

        md_lines = []
        if article.get('title'):
            md_lines.append(f"# {article['title']}")
            md_lines.append('')
        if article.get('author') or article.get('account'):
            meta_parts = []
            if article.get('author'):
                meta_parts.append(f"作者: {article['author']}")
            if article.get('account'):
                meta_parts.append(f"公众号: {article['account']}")
            if article.get('publish_time'):
                meta_parts.append(f"发布时间: {article['publish_time']}")
            md_lines.append(' | '.join(meta_parts))
            md_lines.append('')
        md_lines.append(md_body)

        md_path = os.path.join(article_dir, 'article.md')
        async with aiofiles.open(md_path, 'w', encoding='utf-8') as f:
            await f.write('\n'.join(md_lines))

        json_path = os.path.join(article_dir, 'data.json')
        async with aiofiles.open(json_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(article, ensure_ascii=False, indent=2))

        return {
            'title': article.get('title'),
            'author': article.get('author'),
            'account': article.get('account'),
            'publish_time': article.get('publish_time'),
            'article_dir': article_dir,
            'html_path': html_path,
            'md_path': md_path,
            'json_path': json_path,
            'image_count': len(downloaded_images),
            'downloaded_images': downloaded_images,
        }

    "-------------------------------------------------------main-------------------------------------------------------"

    async def main(self):
        url = "https://mp.weixin.qq.com/s/example"
        result = await self.fetch_article(url)
        print(result)


if __name__ == "__main__":
    crawler = WeChatMpCrawler()
    start = time.time()
    asyncio.run(crawler.main())
    end = time.time()
    print(f"耗时: {end - start}")
