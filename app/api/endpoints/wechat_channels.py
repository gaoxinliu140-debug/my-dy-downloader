from fastapi import APIRouter, Query, Request, HTTPException  # 导入FastAPI组件
from app.api.models.APIResponseModel import ResponseModel, ErrorResponseModel  # 导入响应模型

from crawlers.wechat.channels.channels_crawler import WeChatChannelsCrawler  # 导入微信视频号爬虫


router = APIRouter()
WeChatChannelsCrawler = WeChatChannelsCrawler()


# 解析单个视频号视频地址
@router.get("/fetch_video", response_model=ResponseModel,
            summary="解析单个视频号视频地址/Parse single WeChat Channels video")
async def fetch_video(request: Request,
                      url: str = Query(
                          example="https://weixin.qq.com/sph/example",
                          description="视频号分享链接/WeChat Channels share URL")):
    """
    # [中文]
    ### 用途:
    - 解析单个微信视频号视频，提取标题、作者、封面、描述、点赞和转发数。
    - 视频号视频流地址暂无法通过公开 API 获取，需在微信客户端播放。
    ### 参数:
    - url: 视频号分享链接 (weixin.qq.com/sph 短链 或 channels.weixin.qq.com)
    ### 返回:
    - 视频结构化数据 (title/nickname/cover_url/description/stats)

    # [English]
    ### Purpose:
    - Parse a single WeChat Channels video, extracting title, author, cover, description, and stats.
    - The video stream URL is not available via the public API and requires the WeChat client to play.
    ### Parameters:
    - url: WeChat Channels share URL (weixin.qq.com/sph or channels.weixin.qq.com)
    ### Return:
    - Structured video data (title/nickname/cover_url/description/stats)

    # [示例/Example]
    url = "https://channels.weixin.qq.com/web/pages/feed?..."
    """
    try:
        data = await WeChatChannelsCrawler.fetch_video(url)
        return ResponseModel(code=200,
                             router=request.url.path,
                             data=data)
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    message=str(e)
                                    )
        raise HTTPException(status_code=status_code, detail=detail.dict())


# 获取视频号分享页原始HTML
@router.get("/fetch_page_html", response_model=ResponseModel,
            summary="获取视频号分享页原始HTML/Get raw WeChat Channels page HTML")
async def fetch_page_html(request: Request,
                          url: str = Query(
                              example="https://weixin.qq.com/sph/example",
                              description="视频号分享链接/WeChat Channels share URL")):
    """
    # [中文]
    ### 用途:
    - 获取视频号分享页面的原始 HTML，便于自定义解析。
    ### 参数:
    - url: 视频号分享链接
    ### 返回:
    - 原始 HTML 字符串

    # [English]
    ### Purpose:
    - Get the raw HTML of the WeChat Channels share page for custom parsing.
    ### Parameters:
    - url: WeChat Channels share URL
    ### Return:
    - Raw HTML string

    # [示例/Example]
    url = "https://channels.weixin.qq.com/web/pages/feed?..."
    """
    try:
        real_url = await WeChatChannelsCrawler.resolve_share_url(url)
        data = await WeChatChannelsCrawler.fetch_page_html(real_url)
        return ResponseModel(code=200,
                             router=request.url.path,
                             data={"url": real_url, "html": data})
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    message=str(e)
                                    )
        raise HTTPException(status_code=status_code, detail=detail.dict())
