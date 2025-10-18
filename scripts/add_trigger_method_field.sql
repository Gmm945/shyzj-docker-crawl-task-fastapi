-- 为现有任务添加trigger_method字段
-- 执行前请备份数据库

-- 添加trigger_method字段，默认值为'manual'
ALTER TABLE tasks ADD COLUMN trigger_method VARCHAR(20) DEFAULT 'manual' COMMENT '触发方式：manual-手动，auto-自动';

-- 为现有任务设置默认值
UPDATE tasks SET trigger_method = 'manual' WHERE trigger_method IS NULL;

-- 如果有任务已经有调度配置，将其设置为auto
UPDATE tasks t 
SET trigger_method = 'auto' 
WHERE EXISTS (
    SELECT 1 FROM task_schedules ts 
    WHERE ts.task_id = t.id 
    AND ts.is_active = 1 
    AND ts.is_delete = 0
);

-- 验证更新结果
SELECT 
    id,
    task_name,
    trigger_method,
    status,
    (SELECT COUNT(*) FROM task_schedules ts WHERE ts.task_id = tasks.id AND ts.is_active = 1 AND ts.is_delete = 0) as active_schedules
FROM tasks 
WHERE is_delete = 0
ORDER BY create_time DESC
LIMIT 10;
