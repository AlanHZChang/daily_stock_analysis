# syntax=docker/dockerfile:1.7

# ===================================
# A股自選股智能分析系統 - Docker 鏡像
# ===================================
# 多階段構建：前端打包 + 後端運行

FROM node:20-slim AS web-builder

WORKDIR /app/apps/dsa-web
ARG DSA_WEB_VERSION=0.0.0
ARG DSA_WEB_REVISION=unknown

COPY apps/dsa-web/package.json apps/dsa-web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY apps/dsa-web/ ./
RUN DSA_WEB_VERSION="${DSA_WEB_VERSION}" DSA_WEB_REVISION="${DSA_WEB_REVISION}" npm run build

# Pin to bookworm: wkhtmltopdf was removed from Debian testing (2025)
FROM python:3.11-slim-bookworm

# 設置工作目錄
WORKDIR /app

# 設置時區為上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安裝系統依賴（wkhtmltopdf 含 wkhtmltoimage，用於 Markdown 轉圖片 Issue #289）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    gosu \
    wkhtmltopdf \
    fontconfig \
    fonts-noto-cjk \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 創建非 root 用戶 (UID 1000)
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# 複製應用代碼
COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY --from=web-builder /app/static ./static/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Verify globally bundled runtime dependencies without leaving SDK logs in the image.
RUN mkdir -p /tmp/futu-sdk-smoke-home && \
    HOME=/tmp/futu-sdk-smoke-home python -c "import src.services.screening.pipeline; import futu" && \
    rm -rf /tmp/futu-sdk-smoke-home

# 確保數據目錄存在並授權給 non-root 用戶
RUN mkdir -p /app/data /app/logs /app/reports && \
    chown -R dsa:dsa /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# efinance 將搜索緩存（search-cache.json）寫入自身安裝包內的 data 目錄，
# 該目錄默認歸 root 所有；容器以非 root 用戶 dsa 運行時寫入會 PermissionError，
# 導致 efinance 數據源每次抓取 A 股數據都失敗並降級。預置目錄屬主給 dsa 修復此問題。
# 動態解析路徑，避免寫死 Python 版本目錄。
RUN EF_DATA_DIR="$(python -c 'import efinance, pathlib; print(pathlib.Path(efinance.__file__).parent / "data")')" && \
    mkdir -p "$EF_DATA_DIR" && \
    chown -R dsa:dsa "$EF_DATA_DIR"

# 設置環境變量默認值
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
# Web/API service
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000

# 暴露 API 端口
EXPOSE 8000

# 數據卷（持久化數據）
VOLUME ["/app/data", "/app/logs", "/app/reports"]

# 健康檢查（FastAPI 模式）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(0)"

# 啟動入口先修復 bind mount 目錄權限，再降權為 dsa 執行應用；
# 文檔化 docker-compose exec 命令需顯式使用 -u dsa，避免手動進程寫入 root-owned 文件。
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# 默認命令（可被覆蓋）
CMD ["python", "main.py", "--schedule"]
