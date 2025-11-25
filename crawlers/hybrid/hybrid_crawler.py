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
# 　　　　 　　  ＿＿
# 　　　 　　 ／＞　　フ
# 　　　 　　| 　_　 _ l
# 　 　　 　／` ミ＿xノ
# 　　 　 /　　　 　 |       Feed me Stars ⭐ ️
# 　　　 /　 ヽ　　 ﾉ
# 　 　 │　　|　|　|
# 　／￣|　　 |　|　|
# 　| (￣ヽ＿_ヽ_)__)
# 　＼二つ
# ==============================================================================
#
# Contributor Link:
# - https://github.com/Evil0ctal
#
# ==============================================================================

import asyncio
import re
import httpx

from crawlers.tiktok.web.web_crawler import TikTokWebCrawler  # 导入TikTok Web爬虫
from crawlers.tiktok.app.app_crawler import TikTokAPPCrawler  # 导入TikTok App爬虫


class HybridCrawler:
    def __init__(self):
        self.TikTokWebCrawler = TikTokWebCrawler()
        self.TikTokAPPCrawler = TikTokAPPCrawler()

    async def hybrid_parsing_single_video(self, url: str, minimal: bool = False):
        # 解析TikTok视频/Parse TikTok video
        if "tiktok" in url:
            platform = "tiktok"
            aweme_id = await self.TikTokWebCrawler.get_aweme_id(url)

            # 2024-09-14: Switch to TikTokAPPCrawler instead of TikTokWebCrawler
            # data = await self.TikTokWebCrawler.fetch_one_video(aweme_id)
            # data = data.get("itemInfo").get("itemStruct")

            data = await self.TikTokAPPCrawler.fetch_one_video(aweme_id)
            # $.imagePost exists if aweme_type is photo
            aweme_type = data.get("aweme_type")
        else:
            raise ValueError("Only TikTok URLs are supported. Please provide a valid TikTok video URL.")

        # 检查是否需要返回最小数据/Check if minimal data is required
        if not minimal:
            return data

        # 如果是最小数据，处理数据/If it is minimal data, process the data
        url_type_code_dict = {
            # common
            0: 'video',
            # TikTok
            51: 'video',
            55: 'video',
            58: 'video',
            61: 'video',
            150: 'image'
        }
        # 判断链接类型/Judge link type
        url_type = url_type_code_dict.get(aweme_type, 'video')
        # print(f"url_type: {url_type}")

        """
        以下为(视频||图片)数据处理的四个方法,如果你需要自定义数据处理请在这里修改.
        The following are four methods of (video || image) data processing. 
        If you need to customize data processing, please modify it here.
        """

        """
        创建已知数据字典(索引相同)，稍后使用.update()方法更新数据
        Create a known data dictionary (index the same),
        and then use the .update() method to update the data
        """

        # TikTok data structure
        result_data = {
            'type': url_type,
            'platform': platform,
            'video_id': aweme_id,
            'desc': data.get("desc"),
            'create_time': data.get("create_time"),
            'author': data.get("author"),
            'music': data.get("music"),
            'statistics': data.get("statistics"),
            'cover_data': {},  # 将在各平台处理中填充
            'hashtags': data.get('text_extra'),
        }
        # 创建一个空变量，稍后使用.update()方法更新数据/Create an empty variable and use the .update() method to update the data
        api_data = None
        # 判断链接类型并处理数据/Judge link type and process data
        # TikTok数据处理/TikTok data processing
        if platform == 'tiktok':
            # 填充封面数据
            result_data['cover_data'] = {
                'cover': data.get("video", {}).get("cover"),
                'origin_cover': data.get("video", {}).get("origin_cover"),
                'dynamic_cover': data.get("video", {}).get("dynamic_cover")
            }
            # TikTok视频数据处理/TikTok video data processing
            if url_type == 'video':
                # 将信息储存在字典中/Store information in a dictionary
                # wm_video = data['video']['downloadAddr']
                # wm_video = data['video']['download_addr']['url_list'][0]
                wm_video = (
                    data.get('video', {})
                    .get('download_addr', {})
                    .get('url_list', [None])[0]
                )

                api_data = {
                    'video_data':
                        {
                            'wm_video_url': wm_video,
                            'wm_video_url_HQ': wm_video,
                            # 'nwm_video_url': data['video']['playAddr'],
                            'nwm_video_url': data['video']['play_addr']['url_list'][0],
                            # 'nwm_video_url_HQ': data['video']['bitrateInfo'][0]['PlayAddr']['UrlList'][0]
                            'nwm_video_url_HQ': data['video']['bit_rate'][0]['play_addr']['url_list'][0]
                        }
                }
            # TikTok图片数据处理/TikTok image data processing
            elif url_type == 'image':
                # 无水印图片列表/No watermark image list
                no_watermark_image_list = []
                # 有水印图片列表/With watermark image list
                watermark_image_list = []
                for i in data['image_post_info']['images']:
                    no_watermark_image_list.append(i['display_image']['url_list'][0])
                    watermark_image_list.append(i['owner_watermark_image']['url_list'][0])
                api_data = {
                    'image_data':
                        {
                            'no_watermark_image_list': no_watermark_image_list,
                            'watermark_image_list': watermark_image_list
                        }
                }
        # 更新数据/Update data
        result_data.update(api_data)
        return result_data

    async def main(self):
        # 测试混合解析单一视频接口/Test TikTok parsing single video endpoint
        url = "https://www.tiktok.com/@flukegk83/video/7360734489271700753"
        # url = "https://www.tiktok.com/@minecraft/photo/7369296852669205791"
        minimal = True
        result = await self.hybrid_parsing_single_video(url, minimal=minimal)
        print(result)

        # 占位
        pass


if __name__ == '__main__':
    # 实例化混合爬虫/Instantiate hybrid crawler
    hybird_crawler = HybridCrawler()
    # 运行测试代码/Run test code
    asyncio.run(hybird_crawler.main())
