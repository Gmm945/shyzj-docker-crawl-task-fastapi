# shyzj-docker-crawl-task-fastapi
# 数据采集任务管理系统

一个现代化的、基于 FastAPI 的数据采集任务管理平台，支持多种数据源采集、任务调度和容器化执行。

## 🚀 技术栈

- **包管理**: PDM (Python Dependency Management)
- **Web框架**: FastAPI (异步高性能)
- **数据库**: MySQL + SQLAlchemy ORM
- **缓存**: Redis (高并发心跳数据)
- **异步任务**: Celery + Redis
- **容器化**: Docker + Docker Compose
- **数据库迁移**: Alembic
- **日志**: Loguru

## ✨ 项目特色

### 🎯 现代化开发体验
- 完全基于 **PDM** 包管理，享受现代Python开发标准
- 丰富的内置脚本，一键启动各种服务
- 完善的开发环境配置和文档

### 🏗️ 模块化架构设计
- 参照 AKS 项目结构，采用模块化设计
- 清晰的目录结构和职责分离
- 易于扩展和维护

### 🔧 强大的任务管理
- 支持三种任务类型：Docker爬虫、API调用、数据库操作
- 灵活的任务调度和监控
- 基于 Redis 的任务进度跟踪

### 🐳 容器化支持
- 完整的 Docker 支持
- 支持 Docker 容器执行爬虫任务
- 自动化的容器生命周期管理

## 📁 项目结构

```
src/
├── common/                    # 通用模块
│   └── schemas/              # 通用数据模型
├── config/                   # 配置模块
├── db_util/                  # 数据库工具
├── data_platform_api/        # 主业务模块
│   ├── models/               # 业务模型
│   ├── schemas/              # 业务数据模型
│   ├── routes/               # API 路由
│   └── service/              # 业务逻辑
├── user_manage/              # 用户管理模块
│   ├── models/               # 用户模型
│   ├── schemas/              # 用户数据模型
│   ├── routes/               # 用户API路由
│   └── service/              # 用户业务逻辑
├── worker/                   # 异步任务模块
│   ├── main.py               # 任务入口文件（导入所有任务模块）
│   ├── data_collection_tasks.py  # 数据采集任务
│   ├── docker_management_tasks.py # Docker 容器管理任务
│   ├── monitoring_tasks.py   # 监控和清理任务
│   ├── scheduler_tasks.py    # 调度任务
│   ├── db_tasks.py           # 数据库任务
│   ├── file_tasks.py         # 文件处理任务
│   └── utils/                # 任务工具类
├── utils/                    # 通用工具
└── main.py                   # 应用入口
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+
- Redis 5.0+
- Docker (可选)

### 安装和启动

1. **克隆项目**
```bash
git clone <repository-url>
cd data_plat_project
```

2. **安装 PDM**
```bash
pip install pdm
```

3. **安装依赖**
```bash
pdm install
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库和Redis连接信息
```

5. **初始化数据库**
```bash
pdm run alembic upgrade head
```

6. **启动服务**
```bash
# 启动 API 服务
pdm run start

# 启动 Worker (新终端)
pdm run worker

# 启动调度器 (新终端)
pdm run beat
```

## 📖 详细文档

- [文档目录](docs/README.md) - 完整文档导航
- [安装配置指南](docs/安装配置指南.md) - 详细的安装、配置和部署指南
- [项目架构说明](docs/项目架构说明.md) - 项目架构和设计说明
- [PDM 使用指南](docs/PDM使用指南.md) - PDM 包管理工具使用说明

## 🔧 主要功能

### 用户管理
- 用户注册、登录、权限管理
- JWT 身份验证
- 管理员功能

### 任务管理
- 支持 Docker 爬虫、API 调用、数据库操作
- 任务配置和参数管理
- 任务状态监控和进度跟踪

### 任务调度
- 灵活的定时任务调度
- 支持立即执行、定时执行、周期性执行
- 任务队列管理

### 监控和日志
- 实时任务状态监控
- 详细的执行日志
- 系统健康检查

## 🛠️ 开发指南

### 添加新功能
1. 在对应模块下创建新的路由、服务或模型
2. 更新 API 文档
3. 添加相应的测试

### 数据库迁移
```bash
# 创建迁移文件
pdm run alembic revision --autogenerate -m "描述"

# 执行迁移
pdm run alembic upgrade head
```

### 任务开发
1. 在 `worker/` 目录下添加新的任务类型
2. 在 `celeryconfig.py` 中配置队列路由
3. 在 `celery_beat_schedule.py` 中添加定时配置

## 📊 API 文档

启动服务后，访问以下地址查看 API 文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

如有问题或建议，请通过以下方式联系：
- 创建 Issue
- 发送邮件
- 项目讨论区