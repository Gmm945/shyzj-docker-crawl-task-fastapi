# PDM 使用指南

本项目现已完全支持 PDM (Python Dependency Management) 进行包管理。PDM 是一个现代化的 Python 包管理工具，支持 PEP 621 标准。

## 什么是 PDM？

PDM 是一个现代化的 Python 包管理器，具有以下特点：
- 支持 PEP 621 标准的 `pyproject.toml`
- 快速的依赖解析和安装
- 支持多种 Python 版本
- 内置虚拟环境管理
- 丰富的插件系统

## 安装 PDM

### 方法 1: 使用 pip 安装
```bash
pip install pdm
```

### 方法 2: 使用官方安装脚本
```bash
curl -sSL https://raw.githubusercontent.com/pdm-project/pdm/main/install-pdm.py | python -
```

### 方法 3: 使用 Homebrew (macOS)
```bash
brew install pdm
```

## 项目配置

### pyproject.toml 配置
项目根目录的 `pyproject.toml` 文件包含了完整的项目配置：

```toml
[project]
name = "data-platform"
version = "0.1.0"
description = "数据采集任务管理系统"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0.23",
    "alembic>=1.12.1",
    "pymysql>=1.1.0",
    "cryptography>=41.0.7",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "celery>=5.3.4",
    "redis>=5.0.1",
    "loguru>=0.7.2",
    "docker>=6.1.3",
    "httpx>=0.25.2",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "black>=23.11.0",
    "isort>=5.12.0",
    "flake8>=6.1.0",
    "mypy>=1.7.1",
]

[build-system]
requires = ["pdm-backend"]
build-backend = "pdm.backend"

[tool.pdm]
dev-dependencies = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "black>=23.11.0",
    "isort>=5.12.0",
    "flake8>=6.1.0",
    "mypy>=1.7.1",
]

[tool.pdm.scripts]
start = "uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
worker = "celery -A src.worker.celeryconfig worker --loglevel=info"
beat = "celery -A src.worker.celeryconfig beat --loglevel=info"
test = "pytest"
lint = "flake8 src/"
format = "black src/ && isort src/"
mypy = "mypy src/"
db-upgrade = "alembic upgrade head"
db-downgrade = "alembic downgrade -1"
db-revision = "alembic revision --autogenerate -m"
db-history = "alembic history"
db-current = "alembic current"
```

## 基本使用

### 1. 初始化项目
```bash
# 如果项目还没有 PDM 配置
pdm init

# 安装项目依赖
pdm install
```

### 2. 安装依赖
```bash
# 安装所有依赖（包括开发依赖）
pdm install

# 只安装生产依赖
pdm install --prod

# 安装特定依赖
pdm add fastapi
pdm add pytest --dev
```

### 3. 运行脚本
```bash
# 启动 API 服务
pdm run start

# 启动 Worker
pdm run worker

# 启动调度器
pdm run beat

# 运行测试
pdm run test

# 代码格式化
pdm run format

# 代码检查
pdm run lint
```

### 4. 数据库操作
```bash
# 升级数据库
pdm run db-upgrade

# 降级数据库
pdm run db-downgrade

# 创建迁移文件
pdm run db-revision "描述信息"

# 查看迁移历史
pdm run db-history

# 查看当前版本
pdm run db-current
```

## 高级功能

### 1. 虚拟环境管理
```bash
# 创建虚拟环境
pdm venv create

# 激活虚拟环境
pdm venv activate

# 查看虚拟环境信息
pdm venv info

# 删除虚拟环境
pdm venv remove
```

### 2. 依赖管理
```bash
# 查看依赖树
pdm list --tree

# 查看过时的依赖
pdm list --outdated

# 更新依赖
pdm update

# 更新特定依赖
pdm update fastapi

# 移除依赖
pdm remove package-name
```

### 3. 锁定文件
```bash
# 生成锁定文件
pdm lock

# 从锁定文件安装
pdm install --frozen
```

### 4. 插件系统
```bash
# 安装插件
pdm plugin add pdm-vscode

# 查看已安装的插件
pdm plugin list

# 移除插件
pdm plugin remove plugin-name
```

## 开发工作流

### 1. 新功能开发
```bash
# 1. 创建新分支
git checkout -b feature/new-feature

# 2. 安装开发依赖
pdm install

# 3. 开发代码
# ... 编写代码 ...

# 4. 运行测试
pdm run test

# 5. 代码格式化
pdm run format

# 6. 代码检查
pdm run lint

# 7. 提交代码
git add .
git commit -m "feat: add new feature"
```

### 2. 依赖更新
```bash
# 1. 检查过时的依赖
pdm list --outdated

# 2. 更新依赖
pdm update

# 3. 测试更新后的代码
pdm run test

# 4. 提交更新
git add pyproject.toml pdm.lock
git commit -m "chore: update dependencies"
```

### 3. 发布版本
```bash
# 1. 更新版本号
pdm version patch  # 或 minor, major

# 2. 构建包
pdm build

# 3. 发布到 PyPI
pdm publish
```

## 常见问题

### 1. 依赖冲突
```bash
# 查看依赖冲突
pdm list --tree

# 解决冲突
pdm update --unconstrained
```

### 2. 虚拟环境问题
```bash
# 重新创建虚拟环境
pdm venv remove
pdm venv create
pdm install
```

### 3. 锁定文件问题
```bash
# 重新生成锁定文件
rm pdm.lock
pdm lock
pdm install
```

## 最佳实践

### 1. 依赖管理
- 定期更新依赖
- 使用版本范围而不是固定版本
- 分离开发依赖和生产依赖

### 2. 虚拟环境
- 每个项目使用独立的虚拟环境
- 不要提交虚拟环境到版本控制
- 使用 `.python-version` 文件指定 Python 版本

### 3. 锁定文件
- 提交 `pdm.lock` 文件到版本控制
- 在生产环境使用 `pdm install --frozen`
- 定期更新锁定文件

### 4. 脚本管理
- 将常用命令定义为脚本
- 使用描述性的脚本名称
- 保持脚本的简洁性

## 与 pip 的对比

| 特性 | PDM | pip |
|------|-----|-----|
| 依赖解析 | 快速，支持 PEP 621 | 较慢，基础功能 |
| 虚拟环境 | 内置管理 | 需要 venv |
| 锁定文件 | 自动生成 | 需要 pip-tools |
| 脚本管理 | 内置支持 | 需要额外工具 |
| 插件系统 | 丰富 | 有限 |

## 总结

PDM 为项目提供了现代化的 Python 包管理体验：

1. **快速高效** - 快速的依赖解析和安装
2. **功能丰富** - 内置虚拟环境、脚本管理等功能
3. **标准兼容** - 支持 PEP 621 标准
4. **易于使用** - 简洁的命令行界面
5. **可扩展** - 丰富的插件系统

通过使用 PDM，项目获得了更好的依赖管理、更快的开发体验和更稳定的部署环境。
