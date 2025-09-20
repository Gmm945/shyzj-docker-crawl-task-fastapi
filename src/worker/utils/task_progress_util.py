import json
import traceback
from typing import Optional, Union
from celery import Task
from loguru import logger
from ..celeryconfig import redis_client


class BaseTaskWithProgress(Task):
    abstract = True
    default_namespace: str = "default_task"

    def _status_key(self, task_id: str, namespace: str) -> str:
        return f"{namespace}:status:{task_id}"

    def update_status(
        self,
        progress: int = 0,
        status: str = "PENDING",
        error: Optional[Union[str, Exception]] = None,
        task_id: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        task_id = task_id or self.request.id
        namespace = namespace or self.request.kwargs.get("namespace", self.default_namespace)
        key = self._status_key(task_id, namespace)
        data = {"status": status, "progress": progress}
        
        # 如果 error 是 Exception 类型，转换成详细信息字典
        if isinstance(error, Exception):
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            error_info = {
                "exc_type": type(error).__name__,
                "exc_message": str(error),
                "exc_traceback": tb_str,
            }
            data["error"] = str(error)
            data['error_traceback'] = error_info
        elif error:
            data["error"] = error
            
        try:
            redis_client.set(key, json.dumps(data))
            # 只有状态不是 FAILURE 才调用 update_state，避免 Celery 报错
            if status != "FAILURE":
                self.update_state(state=status, meta={"progress": progress, "error": data.get("error")})
            logger.debug(f"[{namespace}] Task {task_id} updated status: {data}")
        except Exception as e:
            logger.error(f"Failed to update status in Redis for [{namespace}] Task {task_id}: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        namespace = kwargs.get("namespace") or self.default_namespace
        self.update_status(progress=100, status="SUCCESS", task_id=task_id, namespace=namespace)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        namespace = kwargs.get("namespace") or self.default_namespace
        self.update_status(progress=0, status="FAILURE", error=exc, task_id=task_id, namespace=namespace)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        namespace = kwargs.get("namespace") or self.default_namespace
        self.update_status(progress=0, status="RETRY", error=exc, task_id=task_id, namespace=namespace)


def get_task_status(task_id: str, namespace: str = "default_task") -> Optional[dict]:
    """获取任务状态"""
    try:
        key = f"{namespace}:status:{task_id}"
        status_data = redis_client.get(key)
        if status_data:
            return json.loads(status_data)
        return None
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        return None


def clear_task_status(task_id: str, namespace: str = "default_task") -> bool:
    """清除任务状态"""
    try:
        key = f"{namespace}:status:{task_id}"
        redis_client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Failed to clear task status for {task_id}: {e}")
        return False
