-- ================================================
-- 调度系统性能优化 - 数据库索引
-- ================================================
-- 创建时间: 2025-10-16
-- 用途: 优化 task_schedules 表查询性能
-- ================================================

USE your_database_name;  -- 修改为你的数据库名

-- 1. 为活跃调度查询添加复合索引
-- 用途: 优化 Celery Beat 每分钟的调度扫描查询
-- 查询: WHERE is_active = true AND next_run_time <= NOW() AND is_delete = false
DROP INDEX IF EXISTS idx_schedule_active_time ON task_schedules;
CREATE INDEX idx_schedule_active_time 
ON task_schedules(is_active, next_run_time, is_delete);

-- 2. 为任务ID查询添加索引
-- 用途: 优化按任务查询调度配置
-- 查询: WHERE task_id = ? AND is_active = true
DROP INDEX IF EXISTS idx_schedule_task_active ON task_schedules;
CREATE INDEX idx_schedule_task_active 
ON task_schedules(task_id, is_active);

-- 3. 为创建时间查询添加索引
-- 用途: 优化旧调度记录清理
-- 查询: WHERE create_time < ? AND is_active = false
DROP INDEX IF EXISTS idx_schedule_cleanup ON task_schedules;
CREATE INDEX idx_schedule_cleanup 
ON task_schedules(create_time, is_active, is_delete);

-- ================================================
-- 验证索引创建
-- ================================================
SHOW INDEX FROM task_schedules;
