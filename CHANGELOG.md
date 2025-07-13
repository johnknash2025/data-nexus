# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2024-07-13

### Added
- 🏗️ **完全なデータ基盤アーキテクチャ**
  - Docker Compose設定による開発環境
  - Kubernetes manifests for 本番環境
  - 環境変数管理 (.env)

- 💾 **データストレージ層**
  - PostgreSQL 15 (構造化データ)
  - MongoDB 7 (非構造化データ)
  - Redis 7 (キャッシュ・セッション)
  - MinIO (オブジェクトストレージ)

- 🔄 **データ処理・ワークフロー**
  - Apache Airflow 2.7.3
  - スクレイピングワークフロー DAG
  - データ処理パイプライン DAG
  - データ品質チェック機能

- 🌐 **API層**
  - FastAPI RESTful API
  - Pydantic データモデル
  - データベース接続管理
  - 学習データセット生成API

- 🕷️ **スクレイピングサービス**
  - ベーススクレイパークラス
  - 画像スクレイピング機能
  - wandb連携メトリクス追跡
  - PostgreSQL/MongoDB自動保存

- 📈 **分析・可視化**
  - JupyterHub データ分析環境
  - Grafana ダッシュボード設定
  - wandb/MLflow ML実験管理

- ⚙️ **設定・インフラ**
  - PostgreSQL初期化スクリプト
  - Grafana データソース設定
  - Docker requirements管理
  - セットアップスクリプト

### Technical Details
- **16個のPythonファイル** (DAGs, API, サービス)
- **9個のYAML設定ファイル** (Docker, Kubernetes)
- **完全なコンテナ化** (Airflow, API, データベース)
- **マイクロサービス構成** で各コンポーネント独立

### Infrastructure
- TrueNAS Scale (Kubernetes) 対応
- Docker/Docker Compose 開発環境
- 環境変数による設定管理
- ボリューム永続化設定

### Next Steps
- [ ] Docker環境での動作確認
- [ ] Kubernetes環境での展開
- [ ] データパイプライン機能拡張
- [ ] 監視・アラート設定
- [ ] セキュリティ設定強化