from celery.schedules import crontab
from datetime import timedelta

# 时区设置
timezone = "Asia/Shanghai"

# 定时任务配置
beat_schedule = {
    # 处理定时任务 - 每分钟执行一次
    'process-scheduled-tasks': {
        'task': 'process_scheduled_tasks',
        'schedule': crontab(minute='*'),  # 每分钟执行
        'options': {'queue': 'scheduler'}
    },
    
    # 健康检查 - 每5分钟执行一次
    'health-check': {
        'task': 'health_check_task',
        'schedule': crontab(minute='*/5'),  # 每5分钟执行
        'options': {'queue': 'health_check'}
    },
    
    # 清理旧数据 - 每天凌晨2点执行
    'cleanup-old-data': {
        'task': 'cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
        'options': {'queue': 'cleanup'}
    },
    
    # 监控任务执行 - 每30秒执行一次
    'monitor-task-execution': {
        'task': 'monitor_task_execution',
        'schedule': timedelta(seconds=30),  # 每30秒执行
        'options': {'queue': 'monitoring'}
    },
    
    # 清理任务资源 - 每小时执行一次
    'cleanup-task-resources': {
        'task': 'cleanup_task_resources',
        'schedule': crontab(minute=0),  # 每小时执行
        'options': {'queue': 'cleanup'}
    },
}