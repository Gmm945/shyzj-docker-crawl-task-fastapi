"""
调度工具类 - 处理任务调度相关的工具函数
"""
from datetime import datetime, timedelta
from typing import Optional
from ..data_platform_api.models.task import ScheduleType


class ScheduleUtils:
    """调度工具类"""
    
    @staticmethod
    def calculate_next_run_time(schedule_type: ScheduleType, config: dict) -> Optional[datetime]:
        """计算下次执行时间"""
        now = datetime.now()
        
        if schedule_type == ScheduleType.IMMEDIATE:
            return now
        
        elif schedule_type == ScheduleType.SCHEDULED:
            # 指定时间执行：{"datetime": "2024-01-01 12:00:00"}
            scheduled_time = datetime.fromisoformat(config["datetime"])
            return scheduled_time if scheduled_time > now else None
        
        elif schedule_type == ScheduleType.MINUTELY:
            # 每N分钟执行：{"interval": 5}
            interval = config.get("interval", 1)
            return now + timedelta(minutes=interval)
        
        elif schedule_type == ScheduleType.HOURLY:
            # 每N小时执行：{"interval": 2}
            interval = config.get("interval", 1)
            return now + timedelta(hours=interval)
        
        elif schedule_type == ScheduleType.DAILY:
            # 每天指定时间执行：{"time": "09:00:00"}
            time_str = config["time"]
            hour, minute, second = map(int, time_str.split(":"))
            next_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            
            # 如果今天的时间已过，则安排到明天
            if next_time <= now:
                next_time = next_time + timedelta(days=1)
            
            return next_time
        
        elif schedule_type == ScheduleType.WEEKLY:
            # 周调度：{"days": [1, 3, 5], "time": "09:00:00"} # 1=周一
            days = config["days"]
            time_str = config["time"]
            hour, minute, second = map(int, time_str.split(":"))
            
            # 找到下一个执行日期
            for i in range(7):
                check_date = now + timedelta(days=i)
                if check_date.weekday() + 1 in days:  # weekday()返回0-6，我们需要1-7
                    next_time = check_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
                    if next_time > now:
                        return next_time
            
            # 如果本周没有找到，则查找下周
            for i in range(7, 14):
                check_date = now + timedelta(days=i)
                if check_date.weekday() + 1 in days:
                    next_time = check_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
                    return next_time
        
        elif schedule_type == ScheduleType.MONTHLY:
            # 月调度：{"dates": [1, 15], "time": "09:00:00"}
            dates = config["dates"]
            time_str = config["time"]
            hour, minute, second = map(int, time_str.split(":"))
            
            # 查找本月的执行日期
            for date in dates:
                try:
                    next_time = now.replace(day=date, hour=hour, minute=minute, second=second, microsecond=0)
                    if next_time > now:
                        return next_time
                except ValueError:
                    continue  # 日期不存在（如2月30日）
            
            # 如果本月没有找到，查找下个月
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            
            for date in dates:
                try:
                    next_time = next_month.replace(day=date, hour=hour, minute=minute, second=second, microsecond=0)
                    return next_time
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def is_time_to_execute(schedule_type: ScheduleType, config: dict, last_run: Optional[datetime] = None) -> bool:
        """判断是否到了执行时间"""
        next_run_time = ScheduleUtils.calculate_next_run_time(schedule_type, config)
        if not next_run_time:
            return False
        
        now = datetime.now()
        return now >= next_run_time
    
    @staticmethod
    def validate_schedule_config(schedule_type: ScheduleType, config: dict) -> tuple[bool, str]:
        """验证调度配置是否有效"""
        try:
            if schedule_type == ScheduleType.IMMEDIATE:
                return True, "立即执行配置有效"
            
            elif schedule_type == ScheduleType.SCHEDULED:
                if "datetime" not in config:
                    return False, "缺少datetime字段"
                datetime.fromisoformat(config["datetime"])
                return True, "定时执行配置有效"
            
            elif schedule_type == ScheduleType.MINUTELY:
                interval = config.get("interval", 1)
                if not isinstance(interval, int) or interval < 1:
                    return False, "interval必须是大于0的整数"
                return True, "分钟级调度配置有效"
            
            elif schedule_type == ScheduleType.HOURLY:
                interval = config.get("interval", 1)
                if not isinstance(interval, int) or interval < 1:
                    return False, "interval必须是大于0的整数"
                return True, "小时级调度配置有效"
            
            elif schedule_type == ScheduleType.DAILY:
                if "time" not in config:
                    return False, "缺少time字段"
                time_str = config["time"]
                hour, minute, second = map(int, time_str.split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    return False, "time格式无效"
                return True, "每日调度配置有效"
            
            elif schedule_type == ScheduleType.WEEKLY:
                if "days" not in config or "time" not in config:
                    return False, "缺少days或time字段"
                
                days = config["days"]
                if not isinstance(days, list) or not all(1 <= day <= 7 for day in days):
                    return False, "days字段必须是1-7之间的数字列表"
                
                time_str = config["time"]
                hour, minute, second = map(int, time_str.split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    return False, "time格式无效"
                
                return True, "周调度配置有效"
            
            elif schedule_type == ScheduleType.MONTHLY:
                if "dates" not in config or "time" not in config:
                    return False, "缺少dates或time字段"
                
                dates = config["dates"]
                if not isinstance(dates, list) or not all(1 <= date <= 31 for date in dates):
                    return False, "dates字段必须是1-31之间的数字列表"
                
                time_str = config["time"]
                hour, minute, second = map(int, time_str.split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    return False, "time格式无效"
                
                return True, "月调度配置有效"
            
            return False, "未知的调度类型"
            
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"
