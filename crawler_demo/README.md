# 爬虫任务容器化执行 Demo

## 概述

这是一个完整的爬虫任务容器化执行示例，展示了如何构建符合数据采集任务管理系统规范的爬虫Docker镜像。

## 文件夹结构

```
crawler_demo/
├── README.md                 # 本文件
├── Dockerfile               # Docker镜像构建文件
├── requirements.txt         # Python依赖包
├── crawler_service.py       # 爬虫服务主程序
├── config_examples/         # 配置文件示例
│   ├── basic_crawler.json
│   ├── ecommerce_crawler.json
│   └── news_crawler.json
├── test/                    # 测试文件
│   ├── test_crawler.py
│   └── test_heartbeat.py
└── docs/                    # 文档
    ├── 镜像构建规范.md
    ├── 心跳接口说明.md
    └── 使用示例.md
```

## 快速开始

### 1. 构建镜像

```bash
# 构建爬虫镜像
docker build -t crawler-service:latest .
```

### 2. 运行容器

```bash
# 运行爬虫容器
docker run -d \
  --name crawler-demo \
  --rm \
  -v $(pwd)/config_examples/basic_crawler.json:/app/config/config.json:ro \
  -v $(pwd)/output:/app/output \
  -e TASK_EXECUTION_ID=550e8400-e29b-41d4-a716-446655440000 \
  -e CONFIG_PATH=/app/config/config.json \
  -e API_BASE_URL=http://your-api-host:8000 \
  crawler-service:latest
```

### 3. 查看日志

```bash
# 查看容器日志
docker logs -f crawler-demo
```

## 核心特性

- ✅ **心跳保持** - 每30秒发送心跳，包含详细进度信息
- ✅ **优雅停止** - 支持SIGTERM信号处理
- ✅ **进度监控** - 实时报告爬取进度和状态
- ✅ **错误处理** - 单个URL失败不影响整体任务
- ✅ **配置驱动** - 通过JSON配置文件控制爬虫行为

## 环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `TASK_EXECUTION_ID` | 任务执行ID（UUID格式） | `550e8400-e29b-41d4-a716-446655440000` |
| `CONFIG_PATH` | 配置文件路径 | `/app/config/config.json` |
| `API_BASE_URL` | 主控系统API地址 | `http://data-platform-api:8000` |

## 心跳接口

容器会定期向主控系统发送心跳：

```
POST /api/v1/monitoring/heartbeat
```

请求体：
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "container_id": "crawler-container",
  "status": "running",
  "progress": {
    "total_urls": 100,
    "crawled_urls": 45,
    "successful_urls": 42,
    "failed_urls": 3,
    "current_url": "https://example.com/page45",
    "current_stage": "爬取中 (45/100)",
    "data_items": 1250,
    "percentage": 45.0
  },
  "timestamp": 1640995200
}
```

## 完成通知

任务完成时会发送完成通知：

```
POST /api/v1/monitoring/completion
```

请求体：
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "container_id": "crawler-container",
  "success": true,
  "result_data": {
    "crawl_summary": {...},
    "data_items": [...],
    "total_data_count": 1250
  }
}
```

## 重要说明

### Docker镜像配置

- **第三方构建**: 本demo仅作为规范示例，实际的爬虫容器镜像由第三方按照我们的规范构建
- **镜像指定**: 在配置文件中通过 `docker_image` 字段指定要使用的镜像名称
- **镜像命名**: 建议使用 `your-company/crawler-service:latest` 格式
- **规范遵循**: 第三方镜像必须完全遵循[镜像构建规范](docs/镜像构建规范.md)

### 注意事项

1. **镜像命名** - 建议使用 `your-company/crawler-service:latest` 格式
2. **端口暴露** - 不需要暴露任何端口，只通过HTTP请求与主控系统通信
3. **用户权限** - 建议使用非root用户运行
4. **日志输出** - 使用标准输出，便于Docker日志收集
5. **信号处理** - 必须处理SIGTERM信号，实现优雅停止

## 开发指南

详细开发指南请参考 `docs/` 文件夹中的文档：

- [镜像构建规范](docs/镜像构建规范.md)
- [心跳接口说明](docs/心跳接口说明.md)
- [使用示例](docs/使用示例.md)

## 联系支持

如有问题，请联系数据采集任务管理系统开发团队。
