# Worker 模块说明

本模块参照 AKS 项目的 worker 结构设计，提供异步任务处理功能。

## 目录结构

```
worker/
├── __init__.py
├── main.py                    # 主要任务定义（所有 Celery 任务）
├── celeryconfig.py           # Celery 配置
├── data_collection_tasks.py  # 数据采集任务实现
├── docker_management_tasks.py # Docker 容器管理任务实现
├── monitoring_tasks.py       # 监控和清理任务实现
├── scheduler_tasks.py        # 调度任务实现
├── db.py                     # 数据库连接
├── db_tasks.py              # 数据库任务
├── file_tasks.py            # 文件处理任务
└── utils/                   # 工具类
    ├── __init__.py
    └── task_progress_util.py # 任务进度管理
```

## 主要功能

### 1. 主要任务定义 (`main.py`)
所有 Celery 任务都在 `main.py` 中定义，包括：

#### 数据采集任务
- **execute_data_collection_task**: 执行数据采集任务
  - 支持爬虫、API、数据库等多种任务类型
  - 自动创建工作空间和配置文件
  - 实时进度跟踪和状态更新

#### Docker 容器管理任务
- **stop_docker_container**: 停止Docker容器
- **kill_docker_container**: 强制杀死Docker容器
- **get_container_status**: 获取容器状态
- **get_container_logs**: 获取容器日志
- **cleanup_old_containers**: 清理旧容器
- **cleanup_old_configs**: 清理旧配置文件
- **check_docker_host_connection**: 检查Docker主机连接

#### 监控和清理任务
- **monitor_task_execution**: 监控任务执行状态
- **cleanup_task_resources**: 清理任务资源
- **health_check_task**: 系统健康检查
- **cleanup_old_data**: 清理旧数据

#### 调度任务
- **process_scheduled_tasks**: 处理定时任务
- **daily_cleanup_task**: 每日清理任务
- **system_health_check_task**: 系统健康检查任务

### 2. 任务实现模块
各个 `*_tasks.py` 文件包含具体的任务实现逻辑，以 `_impl` 结尾的函数被 `main.py` 中的任务调用。

### 3. 数据库操作 (`db_tasks.py`)
- **save_task_execution_to_db**: 保存任务执行记录
- **update_task_execution_status**: 更新任务执行状态
- **get_task_execution_by_id**: 获取任务执行记录
- **cleanup_old_executions**: 清理旧的执行记录

### 4. 文件处理 (`file_tasks.py`)
- **process_task_config_file**: 处理任务配置文件
- **create_task_workspace**: 创建任务工作空间
- **cleanup_task_files**: 清理任务文件
- **validate_task_config**: 验证任务配置

## 任务队列

| 队列名称 | 用途 | 任务类型 | 说明 |
|---------|------|---------|------|
| task_execution | 任务执行 | 数据采集、API调用、数据库操作 | 主要业务任务 |
| docker_management | Docker管理 | 容器启动、停止、监控、清理 | Docker 相关任务 |
| monitoring | 监控 | 任务监控、资源清理、健康检查 | 监控和清理任务 |
| scheduler | 调度 | 定时任务处理 | 定时调度任务 |
| cleanup | 清理 | 资源清理、数据清理 | 清理相关任务 |
| health_check | 健康检查 | 系统状态检查 | 健康检查任务 |

**注意**: 所有任务都在 `main.py` 中定义，通过 `@celery_app.task` 装饰器注册到 Celery。

## 使用方法

### 启动 Worker

```bash
# 启动所有队列的 worker
celery -A src.worker.celeryconfig worker --loglevel=info

# 启动特定队列的 worker
celery -A src.worker.celeryconfig worker --loglevel=info --queues=task_execution,monitoring

# 启动调度器
celery -A src.worker.celeryconfig beat --loglevel=info
```

### 提交任务

```python
from src.worker.main import execute_data_collection_task

# 提交数据采集任务
result = execute_data_collection_task.delay(
    task_id=task_id,
    execution_id=execution_id,
    config_data=config_data,
    namespace="data_collection"
)
```

### 监控任务状态

```python
from src.worker.utils.task_progress_util import get_task_status

# 获取任务状态
status = get_task_status(task_id, namespace="data_collection")
print(f"任务状态: {status}")
```

## 配置说明

### Redis 配置
- 用于任务状态存储和进度跟踪
- 支持异步和同步操作
- 自动连接管理和错误处理

### 数据库配置
- 使用同步数据库连接
- 支持事务管理
- 自动连接池管理

### 任务进度管理
- 基于 Redis 的进度跟踪
- 支持错误信息记录
- 自动状态更新

## 定时任务

| 任务名称 | 执行频率 | 用途 |
|---------|---------|------|
| process-scheduled-tasks | 每分钟 | 处理定时任务 |
| health-check | 每5分钟 | 系统健康检查 |
| cleanup-old-data | 每天凌晨2点 | 清理旧数据 |
| monitor-task-execution | 每30秒 | 监控任务执行 |
| cleanup-task-resources | 每小时 | 清理任务资源 |

## 错误处理

- 自动重试机制
- 错误日志记录
- 资源自动清理
- 状态回滚

## 扩展说明

### 添加新任务类型

1. 在 `main.py` 中定义新的任务函数
2. 在 `celeryconfig.py` 中配置队列路由
3. 在 `beat_schedule.py` 中添加定时配置（如需要）

### 添加新的数据库操作

1. 在 `db_tasks.py` 中添加新的数据库操作函数
2. 使用 `make_sync_session()` 进行数据库操作
3. 添加适当的错误处理和日志记录

### 添加新的文件处理

1. 在 `file_tasks.py` 中添加新的文件处理函数
2. 遵循统一的错误处理模式
3. 确保资源清理

## 注意事项

1. 所有任务都应该有适当的错误处理
2. 长时间运行的任务应该定期更新进度
3. 确保资源（文件、数据库连接等）得到正确清理
4. 使用适当的日志级别记录重要信息
5. 任务参数应该使用 UUID 而不是整数 ID
