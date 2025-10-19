# 数据采集任务管理系统

## 📖 项目简介

本项目是一个基于 FastAPI、Celery、MySQL、Redis 的数据采集任务管理平台，支持 Docker 容器化任务执行。提供完整的任务管理、调度执行、权限控制等功能。

## 🚀 快速开始

### 环境要求
- **Python**: 3.12 或更高版本
- **MySQL**: 5.7 或更高版本
- **Redis**: 5.0 或更高版本
- **PDM**: 现代化的 Python 依赖管理工具
- **Docker**: 容器化任务执行支持

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd shyzj-docker-crawl-task-fastapi

# 2. 安装 PDM
pip install pdm

# 3. 安装依赖
pdm install

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库和Redis连接信息

# 5. 初始化数据库
pdm run db:reset
pdm run db:init_perm

# 6. 启动服务
pdm run start          # API服务
pdm run celery:all     # Celery服务
```

### 访问系统
- **API文档**: http://localhost:8000/docs
- **管理界面**: http://localhost:8000

## 🏗️ 系统架构

### 核心组件
- **FastAPI** - Web框架和API服务
- **Celery** - 异步任务队列
- **MySQL** - 数据存储
- **Redis** - 缓存和消息队列
- **Docker** - 容器化任务执行

### 主要功能
- 📋 **任务管理** - 创建、编辑、删除数据采集任务
- ⏰ **任务调度** - 支持立即、定时、周期、月度等多种调度策略
- 🐳 **容器化执行** - 在Docker容器中执行爬虫、API、数据库任务
- 💓 **心跳监控** - 实时监控任务执行状态和进度
- 🔄 **异步处理** - 基于Celery的异步任务队列处理
- 👤 **用户管理** - JWT认证和用户管理
- 🔐 **权限管理** - 基于Casbin的RBAC权限控制系统

## 📋 任务管理功能

### 任务类型
- **爬虫任务 (Crawler)** - 网页数据采集
- **API任务 (API)** - 第三方API数据采集
- **数据库任务 (Database)** - 数据库同步和迁移

### 触发方式
- **手动任务** - 通过API接口手动触发执行
- **自动任务** - 根据调度配置自动执行

### 调度类型
- **立即执行** - 任务创建后立即执行
- **定时执行** - 指定时间执行
- **周期执行** - 按小时、天、周、月周期执行
- **Cron表达式** - 支持复杂的Cron调度

## 🔧 配置说明

### 环境变量配置
```bash
# 数据库配置
DATABASE_URL=mysql+asyncmy://root:password@localhost:3306/data_platform

# Redis配置
REDIS_URL=redis://localhost:6379/1

# JWT配置
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Docker配置
DOCKER_REGISTRY=your-registry.com
DOCKER_NAMESPACE=your-namespace
```

### Celery配置
```python
# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=['json']
```

## 📚 详细文档

- **[安装配置](安装配置.md)** - 完整的安装、配置和部署指南
- **[API使用指南](API使用指南.md)** - API接口使用说明和示例

## 🛠️ 开发工具

### PDM 包管理
```bash
# 安装依赖
pdm install

# 运行脚本
pdm run start        # 启动API服务器
pdm run worker       # 启动Worker
pdm run beat         # 启动调度器
pdm run celery:all   # 启动所有Celery服务
```

### 数据库管理
```bash
# 数据库管理命令
pdm run db:reset      # 重置数据库
pdm run db:init_perm  # 初始化权限数据
pdm run db:status     # 查看数据库状态
```

## 🚀 部署指南

### 开发环境
```bash
# 1. 安装依赖
pdm install

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 3. 初始化数据库
pdm run db:reset
pdm run db:init_perm

# 4. 启动服务
pdm run start
pdm run celery:all
```

### 生产环境
```bash
# 1. 使用生产环境配置
export ENVIRONMENT=production

# 2. 启动服务
pdm run start
pdm run celery:all

# 3. 使用进程管理器（推荐）
# 使用 systemd, supervisor 或 pm2 管理进程
```

## 🆘 故障排除

### 常见问题
1. **MySQL连接失败** - 检查服务状态和配置
2. **Redis连接失败** - 验证Redis服务运行
3. **Docker任务失败** - 检查镜像和网络配置
4. **任务超时** - 调整超时设置和资源限制
5. **权限错误** - 检查用户权限和角色配置

### 获取帮助
- 查看详细文档
- 检查日志文件
- 提交Issue反馈

---

📝 **技术特点**: 本项目采用现代化的技术栈，支持Docker容器化任务执行，提供简单直观的使用体验。