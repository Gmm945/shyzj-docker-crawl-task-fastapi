# 爬虫任务容器镜像构建文件
# 符合数据采集任务管理系统规范

FROM python:3.9-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制Python依赖文件
COPY requirements.txt /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制爬虫服务代码
COPY crawler_service.py /app/

# 创建必要的目录
RUN mkdir -p /app/config /app/output

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 创建非root用户
RUN useradd -m -u 1000 crawler && \
    chown -R crawler:crawler /app

# 切换到非root用户
USER crawler

# 健康检查 - 检查爬虫进程是否存在
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python crawler_service.py" || exit 1

# 运行爬虫服务
CMD ["python", "crawler_service.py"]
