# AI Data Platform 使用方法

## 🚀 セットアップ

### 1. TrueNAS Scale での展開

```bash
# リポジトリクローン
git clone <repository-url>
cd data-platform

# セットアップスクリプト実行
./scripts/setup.sh
```

### 2. 手動セットアップ（詳細制御が必要な場合）

```bash
# 環境変数設定
cp .env.example .env
# .env ファイルを編集してパスワードを設定

# Docker Compose での開発環境
docker-compose up -d

# または Kubernetes での本番環境
kubectl apply -f kubernetes/
```

## 📊 アクセス方法

### Airflow WebUI
- URL: `http://<TrueNAS-IP>:8080`
- ユーザー名: `admin`
- パスワード: `.env`ファイルの`AIRFLOW_PASSWORD`

### API エンドポイント
- ベースURL: `http://<TrueNAS-IP>:8000`
- ドキュメント: `http://<TrueNAS-IP>:8000/docs`
- ReDoc: `http://<TrueNAS-IP>:8000/redoc`

## 🔄 主要なワークフロー

### 1. スクレイピングワークフロー
- **DAG名**: `scraping_workflow`
- **実行間隔**: 6時間ごと
- **機能**: 
  - 画像URLスクレイピング
  - PostgreSQL/MongoDBへのデータ保存
  - データ品質チェック
  - 古いデータのクリーンアップ

### 2. データ処理ワークフロー
- **DAG名**: `data_processing_workflow`
- **実行間隔**: 12時間ごと
- **機能**:
  - データ分析・統計生成
  - AI学習用データセット準備
  - データ品質監視

## 🔌 API使用例

### 基本的なデータ取得

```python
import requests

# ベースURL
BASE_URL = "http://<TrueNAS-IP>:8000"

# ヘルスチェック
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 画像データ取得
response = requests.get(f"{BASE_URL}/api/v1/images?limit=10")
images = response.json()
print(f"取得した画像数: {len(images)}")

# データサマリー取得
response = requests.get(f"{BASE_URL}/api/v1/analytics/summary")
summary = response.json()
print(f"総画像数: {summary['total_images']}")
```

### AI学習用データセット取得

```python
# 学習用データセット取得
response = requests.get(f"{BASE_URL}/api/v1/training/dataset?limit=1000")
dataset = response.json()

structured_data = dataset['structured_data']
raw_data = dataset['raw_data']

print(f"構造化データ: {len(structured_data)}件")
print(f"生データ: {len(raw_data)}件")
```

### 画像検索

```python
# テキスト検索
query = "猫"
response = requests.get(f"{BASE_URL}/api/v1/images/search?query={query}&limit=50")
results = response.json()

for image in results:
    print(f"URL: {image['image_url']}")
    print(f"説明: {image['alt_text']}")
    print("---")
```

## 🤖 AIエージェント連携

### 1. データ取得エージェント

```python
class DataRetrievalAgent:
    def __init__(self, api_base_url):
        self.api_url = api_base_url
    
    def get_latest_images(self, count=100):
        """最新の画像データ取得"""
        response = requests.get(f"{self.api_url}/api/v1/images?limit={count}")
        return response.json()
    
    def search_images_by_keyword(self, keyword, limit=50):
        """キーワードで画像検索"""
        response = requests.get(
            f"{self.api_url}/api/v1/images/search",
            params={"query": keyword, "limit": limit}
        )
        return response.json()
    
    def get_training_data(self, limit=1000):
        """学習用データ取得"""
        response = requests.get(
            f"{self.api_url}/api/v1/training/dataset",
            params={"limit": limit, "include_raw": True}
        )
        return response.json()

# 使用例
agent = DataRetrievalAgent("http://<TrueNAS-IP>:8000")
images = agent.get_latest_images(50)
training_data = agent.get_training_data(1000)
```

### 2. 分析エージェント

```python
class AnalyticsAgent:
    def __init__(self, api_base_url):
        self.api_url = api_base_url
    
    def get_data_insights(self):
        """データインサイト取得"""
        summary = requests.get(f"{self.api_url}/api/v1/analytics/summary").json()
        daily_stats = requests.get(f"{self.api_url}/api/v1/analytics/daily-stats").json()
        
        return {
            "summary": summary,
            "trends": daily_stats,
            "recommendations": self._generate_recommendations(summary)
        }
    
    def _generate_recommendations(self, summary):
        """レコメンデーション生成"""
        recommendations = []
        
        if summary['data_quality_score'] < 70:
            recommendations.append("データ品質の改善が必要です")
        
        if summary['last_24h_count'] == 0:
            recommendations.append("過去24時間でデータ収集がありません")
        
        return recommendations
```

## 📈 監視・メトリクス

### wandb連携

```python
# メトリクスをwandbにログ
metrics = {
    "daily_scraped_count": 150,
    "data_quality_score": 85.5,
    "processing_time_seconds": 45.2
}

response = requests.post(
    f"{BASE_URL}/api/v1/wandb/log-metrics",
    json=metrics
)
```

### Grafana ダッシュボード
- PostgreSQLメトリクス監視
- スクレイピング成功率
- データ品質スコア
- API レスポンス時間

## 🔧 管理・メンテナンス

### データクリーンアップ

```bash
# 30日以上古いデータを削除
curl -X POST "http://<TrueNAS-IP>:8000/api/v1/data/cleanup?days=30"

# 重複データの削除
curl -X POST "http://<TrueNAS-IP>:8000/api/v1/data/deduplicate"
```

### ログ確認

```bash
# Airflowログ
kubectl logs -f deployment/airflow-scheduler -n data-platform

# APIログ
kubectl logs -f deployment/api -n data-platform

# PostgreSQLログ
kubectl logs -f deployment/postgres -n data-platform
```

### スケーリング

```bash
# API レプリカ数変更
kubectl scale deployment api --replicas=3 -n data-platform

# リソース使用量確認
kubectl top pods -n data-platform
```

## 🚨 トラブルシューティング

### よくある問題

1. **データベース接続エラー**
   ```bash
   kubectl get pods -n data-platform
   kubectl describe pod <pod-name> -n data-platform
   ```

2. **Airflow DAG が表示されない**
   - DAGファイルの構文エラーをチェック
   - Airflowログを確認

3. **API レスポンスが遅い**
   - Redisキャッシュの状態確認
   - データベースクエリの最適化

### パフォーマンス最適化

1. **データベースインデックス**
   ```sql
   CREATE INDEX CONCURRENTLY idx_scraped_images_alt_text 
   ON scraped_images USING gin(to_tsvector('english', alt_text));
   ```

2. **Redis キャッシュ設定**
   - TTL調整
   - メモリ使用量監視

3. **Kubernetes リソース調整**
   - CPU/メモリリクエスト・リミット
   - HPA (Horizontal Pod Autoscaler) 設定

## 📚 参考資料

- [Airflow Documentation](https://airflow.apache.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [TrueNAS Scale Apps](https://www.truenas.com/docs/scale/)
- [wandb Documentation](https://docs.wandb.ai/)