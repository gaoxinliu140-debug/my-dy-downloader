from fastapi import APIRouter, Query, Request, HTTPException  # 导入FastAPI组件
from app.api.models.APIResponseModel import ResponseModel, ErrorResponseModel  # 导入响应模型

from crawlers.wechat.mp.mp_crawler import WeChatMpCrawler  # 导入微信公众号爬虫


router = APIRouter()
WeChatMpCrawler = WeChatMpCrawler()


# 解析单篇公众号文章
@router.get("/fetch_article", response_model=ResponseModel,
            summary="解析单篇公众号文章/Parse single WeChat official account article")
async def fetch_article(request: Request,
                        url: str = Query(
                            example="https://mp.weixin.qq.com/s/abcdefg",
                            description="公众号文章链接/WeChat MP article URL")):
    """
    # [中文]
    ### 用途:
    - 解析单篇微信公众号文章，提取标题、作者、公众号名称、发布时间、正文文本与图片等信息。
    ### 参数:
    - url: 公众号文章链接 (https://mp.weixin.qq.com/s/...)
    ### 返回:
    - 文章结构化数据

    # [English]
    ### Purpose:
    - Parse a single WeChat official account article, extracting title, author, account name,
      publish time, plain text content and images.
    ### Parameters:
    - url: WeChat MP article URL (https://mp.weixin.qq.com/s/...)
    ### Return:
    - Structured article data

    # [示例/Example]
    url = "https://mp.weixin.qq.com/s/abcdefg"
    """
    try:
        data = await WeChatMpCrawler.fetch_article(url)
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


# 获取公众号文章原始HTML
@router.get("/fetch_article_html", response_model=ResponseModel,
            summary="获取公众号文章原始HTML/Get raw WeChat MP article HTML")
async def fetch_article_html(request: Request,
                             url: str = Query(
                                 example="https://mp.weixin.qq.com/s/abcdefg",
                                 description="公众号文章链接/WeChat MP article URL")):
    """
    # [中文]
    ### 用途:
    - 获取公众号文章页面的原始 HTML，便于自定义解析。
    ### 参数:
    - url: 公众号文章链接
    ### 返回:
    - 原始 HTML 字符串

    # [English]
    ### Purpose:
    - Get the raw HTML of the WeChat MP article page for custom parsing.
    ### Parameters:
    - url: WeChat MP article URL
    ### Return:
    - Raw HTML string

    # [示例/Example]
    url = "https://mp.weixin.qq.com/s/abcdefg"
    """
    try:
        data = await WeChatMpCrawler.fetch_article_html(url)
        return ResponseModel(code=200,
                             router=request.url.path,
                             data={"html": data})
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    message=str(e)
                                    )
        raise HTTPException(status_code=status_code, detail=detail.dict())

@router.get("/download_article", response_model=ResponseModel,
            summary="下载公众号文章（HTML+Markdown+图片）/Download MP article as HTML, Markdown with images")
async def download_article(request: Request,
                           url: str = Query(
                               example="https://mp.weixin.qq.com/s/abcdefg",
                               description="公众号文章链接/WeChat MP article URL"),
                           output_dir: str = Query(
                               default=None,
                               description="下载目录/Output directory (optional)")):
    """
    # [中文]
    ### 用途:
    - 下载公众号文章，保存为 HTML + Markdown 格式，引用的图片自动下载到同级 images/ 目录。
    ### 参数:
    - url: 公众号文章链接
    - output_dir: 下载目录（可选，默认 ./downloads/wechat_mp/）
    ### 返回:
    - 下载结果（文件路径、图片数量等）

    # [English]
    ### Purpose:
    - Download a WeChat MP article as HTML + Markdown with all images saved locally.
    ### Parameters:
    - url: WeChat MP article URL
    - output_dir: Output directory (optional)
    ### Return:
    - Download result with file paths and image count
    """
    try:
        data = await WeChatMpCrawler.download_article(url, output_dir=output_dir)
        return ResponseModel(code=200,
                             router=request.url.path,
                             data=data)
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    message=str(e))
        raise HTTPException(status_code=status_code, detail=detail.dict())