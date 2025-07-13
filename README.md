# AI Data Platform on TrueNAS Scale

TrueNAS Scale上で動作するAIエージェント向けデータ基盤

## 🚀 プロジェクト概要

本プロジェクトは、AIエージェント開発のための包括的なデータ基盤です。スクレイピング、データ処理、機械学習、API提供まで一貫したワークフローを提供します。

## 📊 現在の実装状況

### ✅ 完成済み機能

#### 🏗️ インフラストラクチャ
- **Docker Compose**: 開発環境の完全セットアップ
- **Kubernetes**: 本番環境用マニフェスト
- **環境設定**: `.env`ファイルによる設定管理

#### 💾 データストレージ層
- **PostgreSQL 15**: 構造化データ（画像メタデータ、ジョブ履歴）
- **MongoDB 7**: 非構造化データ（生スクレイピングデータ）
- **Redis 7**: キャッシュ・セッション管理
- **MinIO**: オブジェクトストレージ（画像ファイル）

#### 🔄 データ処理層
- **Apache Airflow 2.7.3**: ワークフロー管理
  - スクレイピングワークフロー
  - データ処理パイプライン
  - データ品質チェック
- **スクレイピングサービス**: 
  - ベーススクレイパークラス
  - 画像スクレイピング機能
  - wandb連携によるメトリクス追跡

#### 🌐 API層
- **FastAPI**: RESTful API
  - データ取得エンドポイント
  - 学習データセット生成
  - 分析レポート機能
- **Pydantic**: データモデル定義

#### 📈 分析・可視化層
- **JupyterHub**: データ分析環境
- **Grafana**: ダッシュボード・可視化
- **wandb/MLflow**: ML実験管理

### 🔧 技術スタック

```yaml
コンテナ: Docker/Kubernetes
ワークフロー: Apache Airflow 2.7.3
API: FastAPI + Uvicorn
データベース: PostgreSQL 15, MongoDB 7
キャッシュ: Redis 7
ストレージ: MinIO
監視: Grafana + Prometheus
ML追跡: wandb, MLflow
```

## 🏗️ アーキテクチャ

```
TrueNAS Scale (Kubernetes)
├── Data Collection Layer
│   ├── Airflow (ワークフロー管理) ✅
│   ├── Scraping Services (コンテナ化済み) ✅
│   └── Data Ingestion APIs ✅
├── Data Storage Layer
│   ├── PostgreSQL (構造化データ) ✅
│   ├── MongoDB (非構造化データ) ✅
│   ├── Redis (キャッシュ) ✅
│   └── MinIO (オブジェクトストレージ) ✅
├── Data Processing Layer
│   ├── Jupyter Hub (データ分析) ✅
│   ├── MLflow (ML実験管理) ✅
│   └── wandb (データ追跡) ✅
├── API Layer
│   ├── FastAPI (データアクセス) ✅
│   └── GraphQL (柔軟なクエリ) 🔄
└── Monitoring
    ├── Grafana (可視化) ✅
    └── Prometheus (メトリクス) 🔄
```

## 📁 ディレクトリ構造

```
data-platform/
├── .env                    # 環境変数設定
├── docker-compose.yml      # 開発環境設定
├── USAGE.md               # 使用方法詳細
├── airflow/               # Airflow設定
│   └── dags/              # ワークフロー定義
├── api/                   # FastAPI アプリケーション
│   ├── main.py            # APIエントリーポイント
│   ├── models.py          # データモデル
│   ├── database.py        # DB接続管理
│   └── services.py        # ビジネスロジック
├── scraping/              # スクレイピングサービス
│   ├── base_scraper.py    # ベースクラス
│   └── image_scraper.py   # 画像スクレイピング
├── docker/                # Dockerfiles
│   ├── airflow/           # Airflow用
│   └── api/               # API用
├── config/                # 設定ファイル
│   ├── postgres/          # PostgreSQL初期化
│   └── grafana/           # Grafana設定
├── kubernetes/            # K8s マニフェスト
└── scripts/               # ユーティリティスクリプト
```

## 🚀 クイックスタート

### 1. 環境設定

```bash
# リポジトリクローン
git clone <repository-url>
cd data-platform

# 環境変数設定
cp .env.example .env
# 必要に応じて .env を編集
```

### 2. 開発環境起動

```bash
# 全サービス起動
docker-compose up -d

# 個別サービス起動
docker-compose up -d postgres mongodb redis minio  # ストレージ層
docker-compose up -d airflow-webserver airflow-scheduler  # Airflow
docker-compose up -d api  # FastAPI
```

### 3. アクセス情報

| サービス | URL | 認証情報 |
|---------|-----|---------|
| Airflow | http://localhost:8080 | admin/admin123 |
| FastAPI | http://localhost:8000 | - |
| Grafana | http://localhost:3000 | admin/admin123 |
| JupyterHub | http://localhost:8888 | - |
| MinIO Console | http://localhost:9001 | admin/admin123 |

## 📈 使用例

### スクレイピングジョブ実行

```python
from scraping.image_scraper import ImageScraper

config = {
    'base_url': 'https://example.com',
    'download_images': True,
    'storage_path': '/data/images'
}

scraper = ImageScraper(config)
result = scraper.run()
```

### API経由でデータ取得

```bash
# データサマリー取得
curl http://localhost:8000/api/v1/data/summary

# 学習データセット生成
curl -X POST http://localhost:8000/api/v1/training/dataset \
  -H "Content-Type: application/json" \
  -d '{"limit": 1000, "format": "json"}'
```

## 🔄 次の開発予定

- [ ] GraphQL API実装
- [ ] Prometheus監視設定
- [ ] セキュリティ強化
- [ ] データパイプライン機能拡張
- [ ] 自動テスト追加

## 📚 詳細ドキュメント

- [使用方法詳細](USAGE.md)
- [API仕様書](http://localhost:8000/docs) (起動後)
- [Airflow DAGs](airflow/dags/)

## 🤝 コントリビューション

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request