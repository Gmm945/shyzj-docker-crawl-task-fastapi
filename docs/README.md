# 数据采集任务管理系统 - 文档中心

## 📖 文档导航

本项目是一个基于 FastAPI、Celery、MySQL、Redis 的数据采集任务管理平台，支持 Docker 容器化任务执行。

### 🚀 快速开始

```bash
# 1. 克隆项目
git clone <repository-url>
cd shyzj-docker-crawl-task-fastapi

# 2. 安装依赖
pdm install

# 3. 初始化数据库
pdm run db:reset

# 4. 初始化权限数据
pdm run python -m src.db_util.init_data

# 5. 启动服务
pdm run start          # API服务（包含权限系统）
pdm run celery:all     # Celery服务
```

### 📚 核心文档

#### 系统架构与配置
- **[项目架构](项目架构.md)** - 系统架构设计和模块说明
- **[安装配置](安装配置.md)** - 完整的安装、配置和部署指南
- **[数据库管理](数据库管理.md)** - 数据库初始化、升级和管理

#### 权限与安全
- **[权限系统使用手册](权限系统使用手册.md)** - Casbin 权限管理完整指南 ⭐ 新增

#### 任务管理
- **[任务执行](任务执行.md)** - Docker容器化任务执行方案
- **[调度执行说明](调度执行说明.md)** - 任务调度配置和使用指南
- **[调度类型快速参考](调度类型快速参考.md)** - 调度类型速查表

#### 监控与维护
- **[Celery配置说明](Celery配置说明.md)** - Celery 和 Beat 配置详解
- **[心跳监控配置](心跳监控配置.md)** - 任务监控和心跳机制

#### API文档
- **[API文档](http://localhost:8089/api/v1/docs)** - 自动生成的API接口文档

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

## 🛠️ 开发工具

### PDM 包管理
```bash
# 安装依赖
pdm install

# 运行脚本
pdm run dev:start    # 启动开发服务器
pdm run worker       # 启动Worker
pdm run beat         # 启动调度器
pdm run db:init      # 初始化数据库
```

### 数据库管理
```bash
# 数据库操作
pdm run db:init      # 初始化数据库
pdm run db:upgrade   # 升级数据库
pdm run db:status    # 查看状态
pdm run db:reset     # 重置数据库
```

## 📊 任务类型

### 1. 爬虫任务 (Crawler)
- 网页数据采集
- 支持多种解析器
- 实时进度监控

### 2. API任务 (API)
- 第三方API数据采集
- 支持认证和限流
- 自动重试机制

### 3. 数据库任务 (Database)
- 数据库同步
- 数据迁移
- 批量处理

## 🔧 配置说明

### 环境变量
```bash
# 数据库配置
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=data_platform

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379

# API配置
SECRET_KEY=your-secret-key
ADMIN_PASSWORD=admin123
```

### Docker配置
```bash
# Docker主机配置
DOCKER_HOST_IP=127.0.0.1
DOCKER_HOST=tcp://remote-docker:2375
API_BASE_URL=http://localhost:8000
```

## 📈 监控和维护

### 健康检查
```bash
# API健康检查
curl http://localhost:8000/health

# 数据库状态
pdm run db:status

# Redis连接
redis-cli ping
```

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看Celery日志
tail -f logs/celery.log
```

## 🚀 部署指南

### 开发环境
```bash
# 1. 安装依赖
pdm install

# 2. 初始化数据库
pdm run db:reset

# 3. 初始化权限数据
pdm run python -m src.db_util.init_data

# 4. 启动服务
pdm run start
pdm run celery:all
```

### 生产环境
```bash
# 1. 备份数据库
mysqldump -u root -p data_platform > backup.sql

# 2. 升级数据库
pdm run db:upgrade

# 3. 启动服务
# 使用 systemd 或 Docker Compose 管理服务
```

## 🆘 故障排除

### 常见问题
1. **MySQL连接失败** - 检查服务状态和配置
2. **Redis连接失败** - 验证Redis服务运行
3. **Docker任务失败** - 检查镜像和网络配置
4. **任务超时** - 调整超时设置和资源限制

### 获取帮助
- 查看详细文档
- 检查日志文件
- 提交Issue反馈

---

📝 **技术特点**: 本项目采用现代化的技术栈，使用简化的SQL脚本进行数据库管理，支持Docker容器化任务执行，提供简单直观的使用体验。