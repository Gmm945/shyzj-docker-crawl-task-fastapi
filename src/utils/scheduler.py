import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db_util.db import sessionmanager
from ..data_platform_api.models.task import TaskSchedule, Task, TaskExecution, ExecutionStatus
from .schedule_utils import ScheduleUtils
from ..worker.celeryconfig import celery_app


class ScheduleManager:
    """任务调度管理器"""
    
    def __init__(self):
        self.schedules: Dict[int, TaskSchedule] = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.load_schedules()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("任务调度器已停止")
    
    def load_schedules(self):
        """从数据库加载所有活跃的调度"""
        try:
            import asyncio
            # 检查是否已经在事件循环中
            try:
                loop = asyncio.get_running_loop()
                # 如果已经在事件循环中，使用 run_in_executor 避免循环冲突
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._load_schedules_async())
                    future.result()
            except RuntimeError:
                # 如果没有运行的事件循环，使用 asyncio.run
                asyncio.run(self._load_schedules_async())
        except Exception as e:
            logger.error(f"加载调度失败: {e}")
    
    async def _load_schedules_async(self):
        """异步加载调度"""
        async with sessionmanager.session() as db:
            result = await db.execute(
                select(TaskSchedule).where(TaskSchedule.is_active == True)
            )
            schedules = result.scalars().all()
            
            with self.lock:
                self.schedules = {schedule.id: schedule for schedule in schedules}
            logger.info(f"加载了 {len(schedules)} 个活跃调度")
    
    def add_schedule(self, schedule: TaskSchedule):
        """添加调度"""
        with self.lock:
            self.schedules[schedule.id] = schedule
        logger.info(f"添加调度: {schedule.id}")
    
    def remove_schedule(self, schedule_id: int):
        """移除调度"""
        with self.lock:
            if schedule_id in self.schedules:
                del self.schedules[schedule_id]
        logger.info(f"移除调度: {schedule_id}")
    
    def update_schedule(self, schedule: TaskSchedule):
        """更新调度"""
        with self.lock:
            if schedule.id in self.schedules:
                self.schedules[schedule.id] = schedule
    
    def _run(self):
        """调度器主循环"""
        while self.running:
            try:
                self._check_and_execute_schedules()
                time.sleep(10)  # 每10秒检查一次
            except Exception as e:
                logger.error(f"调度器运行错误: {e}")
                time.sleep(60)  # 出错后等待1分钟
    
    def _check_and_execute_schedules(self):
        """检查并执行到期的调度"""
        now = datetime.now()
        to_execute = []
        
        with self.lock:
            for schedule_id, schedule in self.schedules.items():
                if schedule.next_run_time and schedule.next_run_time <= now:
                    to_execute.append(schedule)
        
        for schedule in to_execute:
            try:
                self._execute_scheduled_task(schedule)
            except Exception as e:
                logger.error(f"执行调度任务失败 {schedule.id}: {e}")
    
    def _execute_scheduled_task(self, schedule: TaskSchedule):
        """执行调度任务"""
        try:
            import asyncio
            asyncio.run(self._execute_scheduled_task_async(schedule))
        except Exception as e:
            logger.error(f"执行调度任务失败: {e}")
    
    async def _execute_scheduled_task_async(self, schedule: TaskSchedule):
        """异步执行调度任务"""
        async with sessionmanager.session() as db:
            # 获取任务信息
            result = await db.execute(select(Task).where(Task.id == schedule.task_id))
            task = result.scalar_one_or_none()
            
            if not task:
                logger.warning(f"调度任务不存在: {schedule.task_id}")
                return
            
            # 检查是否已有正在运行的任务
            running_result = await db.execute(
                select(TaskExecution).where(
                    TaskExecution.task_id == schedule.task_id,
                    TaskExecution.status == ExecutionStatus.RUNNING
                )
            )
            running_execution = running_result.scalar_one_or_none()
            
            if running_execution:
                logger.info(f"任务 {task.task_name} 正在执行中，跳过此次调度")
                # 更新下次执行时间
                await self._update_next_run_time(schedule, db)
                return
            
            # 创建执行记录
            timestamp = int(datetime.now().timestamp())
            execution_name = f"{timestamp}_{task.task_name}"
            
            db_execution = TaskExecution(
                task_id=schedule.task_id,
                executor_id=task.creator_id,  # 使用任务创建者作为执行者
                execution_name=execution_name,
                status=ExecutionStatus.PENDING
            )
            db.add(db_execution)
            await db.commit()
            await db.refresh(db_execution)
            
            # 提交到Celery执行
            celery_app.send_task(
                'execute_data_collection_task',
                args=[db_execution.id]
            )
            
            # 更新下次执行时间
            await self._update_next_run_time(schedule, db)
            
            logger.info(f"调度执行任务: {task.task_name} (execution_id: {db_execution.id})")
    
    async def _update_next_run_time(self, schedule: TaskSchedule, db: AsyncSession):
        """更新下次执行时间"""
        next_run_time = ScheduleUtils.calculate_next_run_time(schedule.schedule_type, schedule.schedule_config)
        
        if next_run_time:
            schedule.next_run_time = next_run_time
            db.add(schedule)
            await db.commit()
            
            # 更新内存中的调度
            with self.lock:
                if schedule.id in self.schedules:
                    self.schedules[schedule.id] = schedule
        else:
            # 没有下次执行时间，禁用调度
            schedule.is_active = False
            db.add(schedule)
            await db.commit()
            
            # 从内存中移除
            self.remove_schedule(schedule.id)


# 全局调度管理器实例
schedule_manager = ScheduleManager()
