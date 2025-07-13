"""
データ基盤API - AIエージェント向けデータアクセス
"""
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os

from database import get_db_session, get_mongo_client
from models import ImageData, DataSummary, TrainingDataset
from services import DataService, AnalyticsService

# FastAPIアプリケーション初期化
app = FastAPI(
    title="AI Data Platform API",
    description="TrueNAS Scale上で動作するAIエージェント向けデータ基盤API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービス初期化
data_service = DataService()
analytics_service = AnalyticsService()

@app.get("/")
async def root():
    """ヘルスチェック"""
    return {
        "message": "AI Data Platform API",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """詳細ヘルスチェック"""
    try:
        # データベース接続チェック
        db_status = await data_service.check_database_connection()
        mongo_status = await data_service.check_mongodb_connection()
        
        return {
            "status": "healthy",
            "services": {
                "postgresql": db_status,
                "mongodb": mongo_status,
                "api": "healthy"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# データ取得エンドポイント
@app.get("/api/v1/images", response_model=List[ImageData])
async def get_images(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    source_url: Optional[str] = None,
    file_extension: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
):
    """画像データ取得"""
    try:
        filters = {}
        if source_url:
            filters['source_url'] = source_url
        if file_extension:
            filters['file_extension'] = file_extension
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
            
        images = await data_service.get_images(
            limit=limit, 
            offset=offset, 
            filters=filters
        )
        return images
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/images/{image_id}")
async def get_image_by_id(image_id: int):
    """特定画像データ取得"""
    try:
        image = await data_service.get_image_by_id(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        return image
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/images/search")
async def search_images(
    query: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500)
):
    """画像検索（alt_text, page_titleで検索）"""
    try:
        results = await data_service.search_images(query, limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 分析・統計エンドポイント
@app.get("/api/v1/analytics/summary", response_model=DataSummary)
async def get_data_summary():
    """データサマリー取得"""
    try:
        summary = await analytics_service.get_data_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/daily-stats")
async def get_daily_stats(days: int = Query(30, ge=1, le=365)):
    """日別統計取得"""
    try:
        stats = await analytics_service.get_daily_stats(days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/source-stats")
async def get_source_stats():
    """ソース別統計取得"""
    try:
        stats = await analytics_service.get_source_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# AI学習用データエンドポイント
@app.get("/api/v1/training/dataset", response_model=TrainingDataset)
async def get_training_dataset(
    limit: int = Query(1000, ge=1, le=10000),
    include_raw: bool = Query(True),
    min_alt_text_length: int = Query(5, ge=0)
):
    """AI学習用データセット取得"""
    try:
        dataset = await data_service.get_training_dataset(
            limit=limit,
            include_raw=include_raw,
            min_alt_text_length=min_alt_text_length
        )
        return dataset
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/training/embeddings")
async def get_embeddings_data(
    limit: int = Query(500, ge=1, le=5000)
):
    """埋め込み学習用データ取得"""
    try:
        data = await data_service.get_embeddings_data(limit)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# データ管理エンドポイント
@app.post("/api/v1/data/cleanup")
async def cleanup_old_data(days: int = Query(30, ge=1, le=365)):
    """古いデータのクリーンアップ"""
    try:
        result = await data_service.cleanup_old_data(days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/data/deduplicate")
async def deduplicate_data():
    """重複データの削除"""
    try:
        result = await data_service.deduplicate_data()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# wandb連携エンドポイント
@app.post("/api/v1/wandb/log-metrics")
async def log_metrics_to_wandb(metrics: Dict[str, Any]):
    """wandbにメトリクスをログ"""
    try:
        if not os.getenv('WANDB_API_KEY'):
            raise HTTPException(status_code=400, detail="wandb API key not configured")
            
        result = await analytics_service.log_to_wandb(metrics)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# リアルタイムデータストリーム（WebSocket対応）
@app.websocket("/ws/data-stream")
async def websocket_data_stream(websocket):
    """リアルタイムデータストリーム"""
    await websocket.accept()
    try:
        while True:
            # 最新データを定期的に送信
            latest_data = await data_service.get_latest_data()
            await websocket.send_json(latest_data)
            await asyncio.sleep(30)  # 30秒間隔
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)