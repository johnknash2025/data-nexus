#!/bin/bash

# AI Data Platform セットアップスクリプト for TrueNAS Scale

set -e

echo "🚀 AI Data Platform セットアップを開始します..."

# 色付きログ関数
log_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# 環境チェック
check_requirements() {
    log_info "環境要件をチェックしています..."
    
    # kubectl チェック
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl が見つかりません。TrueNAS Scale でkubectlを有効にしてください。"
        exit 1
    fi
    
    # Docker チェック
    if ! command -v docker &> /dev/null; then
        log_error "Docker が見つかりません。"
        exit 1
    fi
    
    log_info "✅ 環境要件チェック完了"
}

# シークレット生成
generate_secrets() {
    log_info "シークレットを生成しています..."
    
    # Fernet key生成
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    
    # パスワード生成
    POSTGRES_PASSWORD=$(openssl rand -base64 32)
    MONGO_PASSWORD=$(openssl rand -base64 32)
    AIRFLOW_PASSWORD=$(openssl rand -base64 32)
    
    # .env ファイル作成
    cat > .env << EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
MONGO_PASSWORD=${MONGO_PASSWORD}
AIRFLOW_FERNET_KEY=${FERNET_KEY}
AIRFLOW_PASSWORD=${AIRFLOW_PASSWORD}
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=$(openssl rand -base64 32)
GRAFANA_PASSWORD=$(openssl rand -base64 32)
EOF
    
    log_info "✅ シークレット生成完了 (.env ファイルを確認してください)"
}

# Dockerイメージビルド
build_images() {
    log_info "Dockerイメージをビルドしています..."
    
    # Airflowイメージビルド
    docker build -t data-platform/airflow:latest -f docker/airflow/Dockerfile .
    
    # APIイメージビルド
    docker build -t data-platform/api:latest -f docker/api/Dockerfile ./api
    
    log_info "✅ Dockerイメージビルド完了"
}

# Kubernetes namespace作成
create_namespace() {
    log_info "Kubernetes namespaceを作成しています..."
    
    kubectl apply -f kubernetes/namespace.yaml
    
    log_info "✅ Namespace作成完了"
}

# Kubernetes secrets作成
create_k8s_secrets() {
    log_info "Kubernetes secretsを作成しています..."
    
    source .env
    
    # データベースシークレット
    kubectl create secret generic db-secrets \
        --from-literal=postgres-password="${POSTGRES_PASSWORD}" \
        --from-literal=mongo-password="${MONGO_PASSWORD}" \
        --namespace=data-platform \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Airflowシークレット
    kubectl create secret generic airflow-secrets \
        --from-literal=fernet-key="${AIRFLOW_FERNET_KEY}" \
        --from-literal=admin-password="${AIRFLOW_PASSWORD}" \
        --namespace=data-platform \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_info "✅ Kubernetes secrets作成完了"
}

# データベース展開
deploy_databases() {
    log_info "データベースを展開しています..."
    
    kubectl apply -f kubernetes/postgres-deployment.yaml
    kubectl apply -f kubernetes/mongodb-deployment.yaml
    
    # データベース起動待機
    log_info "データベースの起動を待機しています..."
    kubectl wait --for=condition=ready pod -l app=postgres --namespace=data-platform --timeout=300s
    kubectl wait --for=condition=ready pod -l app=mongodb --namespace=data-platform --timeout=300s
    
    log_info "✅ データベース展開完了"
}

# Airflow展開
deploy_airflow() {
    log_info "Airflowを展開しています..."
    
    kubectl apply -f kubernetes/airflow-deployment.yaml
    
    # Airflow起動待機
    log_info "Airflowの起動を待機しています..."
    kubectl wait --for=condition=ready pod -l app=airflow-webserver --namespace=data-platform --timeout=600s
    
    log_info "✅ Airflow展開完了"
}

# API展開
deploy_api() {
    log_info "APIサービスを展開しています..."
    
    kubectl apply -f kubernetes/api-deployment.yaml
    
    log_info "✅ API展開完了"
}

# 初期データセットアップ
setup_initial_data() {
    log_info "初期データをセットアップしています..."
    
    # PostgreSQLテーブル作成
    kubectl exec -it deployment/postgres --namespace=data-platform -- psql -U admin -d data_platform -c "
    CREATE TABLE IF NOT EXISTS scraped_images (
        id SERIAL PRIMARY KEY,
        source_url TEXT NOT NULL,
        image_url TEXT NOT NULL UNIQUE,
        alt_text TEXT,
        page_title TEXT,
        file_extension VARCHAR(10),
        has_local_copy BOOLEAN DEFAULT FALSE,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_scraped_images_source_url ON scraped_images(source_url);
    CREATE INDEX IF NOT EXISTS idx_scraped_images_scraped_at ON scraped_images(scraped_at);
    "
    
    log_info "✅ 初期データセットアップ完了"
}

# ヘルスチェック
health_check() {
    log_info "システムヘルスチェックを実行しています..."
    
    # サービス状態確認
    kubectl get pods --namespace=data-platform
    kubectl get services --namespace=data-platform
    
    # API ヘルスチェック
    API_URL=$(kubectl get service api-service --namespace=data-platform -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$API_URL" ]; then
        curl -f http://${API_URL}:8000/health || log_warn "API ヘルスチェックに失敗しました"
    fi
    
    log_info "✅ ヘルスチェック完了"
}

# アクセス情報表示
show_access_info() {
    log_info "🎉 セットアップが完了しました！"
    
    echo ""
    echo "📊 アクセス情報:"
    echo "----------------------------------------"
    
    # Airflow WebUI
    AIRFLOW_IP=$(kubectl get service airflow-webserver-service --namespace=data-platform -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$AIRFLOW_IP" ]; then
        echo "🔄 Airflow WebUI: http://${AIRFLOW_IP}:8080"
        echo "   ユーザー名: admin"
        echo "   パスワード: $(grep AIRFLOW_PASSWORD .env | cut -d'=' -f2)"
    fi
    
    # API エンドポイント
    API_IP=$(kubectl get service api-service --namespace=data-platform -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$API_IP" ]; then
        echo "🔌 API エンドポイント: http://${API_IP}:8000"
        echo "   ドキュメント: http://${API_IP}:8000/docs"
    fi
    
    echo ""
    echo "📝 次のステップ:"
    echo "1. Airflow WebUIでDAGを有効化"
    echo "2. APIエンドポイントでデータ確認"
    echo "3. wandb API keyを設定（オプション）"
    echo ""
    echo "🔧 管理コマンド:"
    echo "kubectl get pods -n data-platform  # ポッド状態確認"
    echo "kubectl logs -f deployment/airflow-scheduler -n data-platform  # Airflowログ確認"
    echo ""
}

# メイン実行
main() {
    echo "🤖 AI Data Platform for TrueNAS Scale"
    echo "======================================"
    
    check_requirements
    generate_secrets
    build_images
    create_namespace
    create_k8s_secrets
    deploy_databases
    deploy_airflow
    deploy_api
    setup_initial_data
    health_check
    show_access_info
}

# スクリプト実行
main "$@"