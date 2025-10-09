# Celery 配置说明

## 📋 配置文件位置
**文件路径**: `src/worker/celeryconfig.py`

这是系统**实际使用**的 Celery 配置文件，包含：
- Celery 应用配置
- Redis 连接配置
- 任务队列配置
- Beat 定时任务配置
- 任务路由规则
---

## 🕐 Celery Beat 定时任务配置

### 当前配置的定时任务

| 任务名称 | 任务函数 | 执行频率 | 队列 | 说明 |
|---------|---------|---------|------|------|
| **process-scheduled-tasks** | `process_scheduled_tasks` | 每分钟 | scheduler | **核心调度任务** ⭐ |
| heartbeat-monitor | `heartbeat_monitor_task` | 每2分钟 | monitoring | 心跳监控 |
| monitor-task-execution | `monitor_task_execution` | 每30秒 | monitoring | 监控任务执行 |
| system-health-check | `system_health_check_task` | 每5分钟 | health_check | 系统健康检查 |
| cleanup-old-data | `cleanup_old_data` | 每天02:00 | cleanup | 清理旧数据 |
| cleanup-task-resources | `cleanup_task_resources` | 每小时 | cleanup | 清理任务资源 |
| daily-cleanup | `daily_cleanup_task` | 每天03:00 | cleanup | 每日清理 |

---

## 🔧 配置详解

### 核心调度任务 (最重要！)

```python
'process-scheduled-tasks': {
    'task': 'process_scheduled_tasks',
    'schedule': crontab(minute='*'),  # 每分钟执行
    'options': {'queue': 'scheduler'}
}
```

**作用**：
- 每分钟检查数据库中的任务调度配置
- 查找 `next_run_time <= 当前时间` 的调度
- 自动触发到期的任务执行
- 更新下次执行时间

**重要性**：⭐⭐⭐⭐⭐  
这是整个调度系统的核心！没有这个任务，所有的调度配置都不会被执行。

---

### 监控任务

#### 1. 心跳监控
```python
'heartbeat-monitor': {
    'task': 'heartbeat_monitor_task',
    'schedule': timedelta(seconds=120),  # 2分钟
    'options': {'queue': 'monitoring'}
}
```
**作用**：检测任务心跳超时，标记失联的任务

#### 2. 任务执行监控
```python
'monitor-task-execution': {
    'task': 'monitor_task_execution',
    'schedule': timedelta(seconds=30),  # 30秒
    'options': {'queue': 'monitoring'}
}
```
**作用**：监控所有任务的执行状态

---

### 清理任务

#### 1. 清理旧数据
```python
'cleanup-old-data': {
    'task': 'cleanup_old_data',
    'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
    'options': {'queue': 'cleanup'}
}
```
**作用**：清理超过指定天数的旧执行记录

#### 2. 清理任务资源
```python
'cleanup-task-resources': {
    'task': 'cleanup_task_resources',
    'schedule': crontab(minute=0),  # 每小时
    'options': {'queue': 'cleanup'}
}
```
**作用**：清理临时文件、停止的容器等资源

---

## 📊 任务队列配置

系统定义了以下任务队列：

| 队列名称 | 说明 | 处理的任务 |
|---------|------|-----------|
| **default** | 默认队列 | 未指定队列的任务 |
| **task_execution** | 任务执行队列 | 数据采集任务 |
| **docker_management** | Docker管理队列 | 容器管理操作 |
| **monitoring** | 监控队列 | 监控和心跳任务 |
| **scheduler** | 调度队列 | 调度处理任务 |
| **cleanup** | 清理队列 | 清理和维护任务 |
| **health_check** | 健康检查队列 | 系统健康检查 |

---

## 🚀 启动服务

### 方式一：使用 PDM (推荐)

```bash
# 1. 启动 Celery Worker
pdm run worker

# 2. 启动 Celery Beat (调度器)
pdm run beat

# 3. 启动 Flower (监控界面)
pdm run flower
```

### 方式二：直接命令

```bash
# 1. 启动 Worker
celery -A src.worker.main worker \
  -Q task_execution,docker_management,monitoring,scheduler,cleanup,health_check \
  -l info --concurrency=4

# 2. 启动 Beat
celery -A src.worker.main beat --loglevel=info

# 3. 启动 Flower
celery -A src.worker.main flower --port=5555 --basic_auth=admin:admin123
```

---

## 📝 验证配置

### 1. 查看 Beat 日志

```bash
# 启动后查看日志
tail -f celery_beat.log

# 应该能看到类似输出：
# [INFO/MainProcess] Scheduler: Sending due task process-scheduled-tasks (process_scheduled_tasks)
```

### 2. 检查调度任务

```bash
# 查看已调度的任务
celery -A src.worker.main inspect scheduled

# 查看活跃的任务
celery -A src.worker.main inspect active
```

### 3. 访问 Flower 监控

打开浏览器访问：http://localhost:5555
- 用户名：`admin`
- 密码：`admin123`

在 Flower 中可以查看：
- Beat 调度情况
- 任务执行历史
- Worker 状态
- 队列情况

---

## 🔍 配置修改指南

### 如何添加新的定时任务？

**步骤**：

1. 在 `src/worker/main.py` 中定义任务函数：
```python
@celery_app.task(
    name="your_new_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="your_queue",
)
def your_new_task(self, namespace: str = "your_namespace"):
    """你的新任务"""
    return your_task_impl(self, namespace)
```

2. 在 `src/worker/celeryconfig.py` 的 `beat_schedule` 中添加配置：
```python
beat_schedule = {
    # ... 现有配置 ...
    
    # 你的新任务
    'your-new-task': {
        'task': 'your_new_task',
        'schedule': crontab(minute='*/10'),  # 每10分钟
        'options': {'queue': 'your_queue'}
    },
}
```

3. 在 `task_routes` 中添加路由：
```python
celery_app.conf.task_routes = {
    # ... 现有路由 ...
    "your_new_task": {"queue": "your_queue"},
}
```

4. 重启 Celery Beat 和 Worker

---

## ⚙️ 调度频率配置

### 使用 crontab

```python
from celery.schedules import crontab

# 每分钟
'schedule': crontab(minute='*')

# 每5分钟
'schedule': crontab(minute='*/5')

# 每小时
'schedule': crontab(minute=0)

# 每天凌晨2点
'schedule': crontab(hour=2, minute=0)

# 每周一早上9点
'schedule': crontab(hour=9, minute=0, day_of_week=1)

# 每月1号凌晨3点
'schedule': crontab(hour=3, minute=0, day_of_month=1)
```

### 使用 timedelta

```python
from datetime import timedelta

# 每30秒
'schedule': timedelta(seconds=30)

# 每2分钟
'schedule': timedelta(minutes=2)

# 每小时
'schedule': timedelta(hours=1)

# 每天
'schedule': timedelta(days=1)
```

---

## 🐛 故障排查

### 问题 1：定时任务不执行

**检查步骤**：

1. **确认 Beat 服务正在运行**
```bash
ps aux | grep "celery.*beat"
```

2. **查看 Beat 日志**
```bash
tail -f celery_beat.log
```

3. **检查任务是否在配置中**
```bash
# 查看配置
grep -n "process-scheduled-tasks" src/worker/celeryconfig.py
```

4. **确认 Worker 正在监听对应队列**
```bash
celery -A src.worker.main inspect active_queues
```

---

### 问题 2：任务重复执行

**原因**：可能启动了多个 Beat 实例

**解决**：
```bash
# 停止所有 Beat 进程
pkill -f "celery.*beat"

# 只启动一个 Beat
pdm run beat
```

⚠️ **重要**：Celery Beat 在整个系统中**只能运行一个实例**！

---

### 问题 3：任务延迟执行

**可能原因**：
1. Worker 数量不足
2. 任务执行时间过长
3. 队列阻塞

**解决方案**：
```bash
# 增加 Worker 并发数
celery -A src.worker.main worker -Q scheduler --concurrency=8

# 检查队列长度
celery -A src.worker.main inspect reserved

# 查看慢任务
celery -A src.worker.main inspect stats
```

---

## 📚 相关文档

- [调度执行说明](./调度执行说明.md) - 用户级的调度使用指南
- [任务执行](./任务执行.md) - Docker 容器化任务执行
- [项目架构](./项目架构.md) - 系统整体架构

---

## 📞 技术支持

如遇到问题，请：
1. 查看 Celery Beat 日志：`celery_beat.log`
2. 查看 Celery Worker 日志
3. 访问 Flower 监控界面
4. 提交 Issue

---

**更新时间**: 2025-10-09  
**维护者**: Data Platform Team  
**配置文件**: `src/worker/celeryconfig.py`

