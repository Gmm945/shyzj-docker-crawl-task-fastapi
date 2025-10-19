# API使用指南

## 概述

本文档介绍数据采集任务管理系统的API接口使用方法，包括认证、任务管理、调度管理等核心功能。

## 认证

### 获取访问令牌

```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

**响应示例**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 18000
}
```

### 使用令牌

在所有API请求中添加Authorization头：
```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://localhost:8000/api/v1/tasks"
```

## 任务管理

### 创建手动任务

```bash
curl -X POST "http://localhost:8000/api/v1/task/add" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "task_name": "手动任务示例",
    "task_type": "api",
    "trigger_method": "manual",
    "base_url": "https://httpbin.org/get",
    "description": "这是一个手动任务示例"
  }'
```

### 创建自动任务

```bash
curl -X POST "http://localhost:8000/api/v1/task/add" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "task_name": "自动任务示例",
    "task_type": "api",
    "trigger_method": "auto",
    "base_url": "https://httpbin.org/get",
    "description": "这是一个自动任务示例",
    "schedule_type": "hourly",
    "schedule_config": {
      "interval": 2
    }
  }'
```

### 获取任务列表

```bash
curl -X GET "http://localhost:8000/api/v1/task/list?page=1&size=10" \
  -H "Authorization: Bearer <your-token>"
```

### 获取任务详情

```bash
curl -X GET "http://localhost:8000/api/v1/task/{task_id}" \
  -H "Authorization: Bearer <your-token>"
```

### 更新任务

```bash
curl -X PUT "http://localhost:8000/api/v1/task/{task_id}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "task_name": "更新后的任务名称",
    "description": "更新后的描述"
  }'
```

### 删除任务

```bash
curl -X DELETE "http://localhost:8000/api/v1/task/{task_id}" \
  -H "Authorization: Bearer <your-token>"
```

### 执行任务

```bash
curl -X POST "http://localhost:8000/api/v1/task/{task_id}/execute" \
  -H "Authorization: Bearer <your-token>"
```

## 调度管理

### 创建调度

```bash
curl -X POST "http://localhost:8000/api/v1/scheduler/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "task_id": "task-uuid",
    "schedule_type": "daily",
    "schedule_config": {
      "time": "10:00:00"
    }
  }'
```

### 获取任务调度

```bash
curl -X GET "http://localhost:8000/api/v1/scheduler/task/{task_id}" \
  -H "Authorization: Bearer <your-token>"
```

### 更新调度

```bash
curl -X PUT "http://localhost:8000/api/v1/scheduler/{schedule_id}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "schedule_type": "weekly",
    "schedule_config": {
      "days": [1, 3, 5],
      "time": "14:30:00"
    }
  }'
```

### 删除调度

```bash
curl -X DELETE "http://localhost:8000/api/v1/scheduler/{schedule_id}" \
  -H "Authorization: Bearer <your-token>"
```

## 调度类型配置

### 分钟调度 (minutely)
```json
{
  "schedule_type": "minutely",
  "schedule_config": {
    "interval": 5
  }
}
```

### 小时调度 (hourly)
```json
{
  "schedule_type": "hourly",
  "schedule_config": {
    "interval": 2
  }
}
```

### 日调度 (daily)
```json
{
  "schedule_type": "daily",
  "schedule_config": {
    "time": "10:00:00"
  }
}
```

### 周调度 (weekly)
```json
{
  "schedule_type": "weekly",
  "schedule_config": {
    "days": [1, 3, 5],
    "time": "14:30:00"
  }
}
```

### 月调度 (monthly)
```json
{
  "schedule_type": "monthly",
  "schedule_config": {
    "dates": [1, 15],
    "time": "09:00:00"
  }
}
```

### Cron调度 (cron)
```json
{
  "schedule_type": "cron",
  "schedule_config": {
    "cron_expression": "0 0 * * *"
  }
}
```

## 任务类型

### 爬虫任务 (crawler)
```json
{
  "task_name": "爬虫任务",
  "task_type": "crawler",
  "trigger_method": "manual",
  "base_url": "https://example.com",
  "extract_config": {
    "selectors": {
      "title": "h1",
      "content": ".content"
    }
  }
}
```

### API任务 (api)
```json
{
  "task_name": "API任务",
  "task_type": "api",
  "trigger_method": "manual",
  "base_url": "https://api.example.com/data",
  "base_url_params": [
    {
      "key": "api_key",
      "value": "your-api-key"
    }
  ]
}
```

### 数据库任务 (database)
```json
{
  "task_name": "数据库任务",
  "task_type": "database",
  "trigger_method": "manual",
  "extract_config": {
    "sql": "SELECT * FROM users WHERE created_at > '2024-01-01'"
  }
}
```

## 错误处理

### 常见错误码

- **400 Bad Request** - 请求参数错误
- **401 Unauthorized** - 认证失败
- **403 Forbidden** - 权限不足
- **404 Not Found** - 资源不存在
- **422 Unprocessable Entity** - 数据验证失败
- **500 Internal Server Error** - 服务器内部错误

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 参数验证错误

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "task_name"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

## 最佳实践

### 1. 任务设计
- 任务名称要具有描述性
- 合理设置任务超时时间
- 考虑任务执行频率和资源消耗

### 2. 调度配置
- 避免过于频繁的调度
- 考虑系统负载和资源限制
- 使用合适的调度类型

### 3. 错误处理
- 实现重试机制
- 记录详细的错误日志
- 设置适当的超时时间

### 4. 性能优化
- 使用分页查询任务列表
- 避免频繁的API调用
- 合理使用缓存

## 示例代码

### Python示例

```python
import requests

# 获取访问令牌
def get_token(username, password):
    response = requests.post(
        "http://localhost:8000/api/v1/auth/token",
        data={"username": username, "password": password}
    )
    return response.json()["access_token"]

# 创建任务
def create_task(token, task_data):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        "http://localhost:8000/api/v1/task/add",
        json=task_data,
        headers=headers
    )
    return response.json()

# 使用示例
token = get_token("admin", "admin123")
task_data = {
    "task_name": "Python API任务",
    "task_type": "api",
    "trigger_method": "manual",
    "base_url": "https://httpbin.org/get"
}
result = create_task(token, task_data)
print(result)
```

### JavaScript示例

```javascript
// 获取访问令牌
async function getToken(username, password) {
  const response = await fetch('http://localhost:8000/api/v1/auth/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: `username=${username}&password=${password}`
  });
  const data = await response.json();
  return data.access_token;
}

// 创建任务
async function createTask(token, taskData) {
  const response = await fetch('http://localhost:8000/api/v1/task/add', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(taskData)
  });
  return await response.json();
}

// 使用示例
(async () => {
  const token = await getToken('admin', 'admin123');
  const taskData = {
    task_name: 'JavaScript API任务',
    task_type: 'api',
    trigger_method: 'manual',
    base_url: 'https://httpbin.org/get'
  };
  const result = await createTask(token, taskData);
  console.log(result);
})();
```

## 总结

本文档涵盖了数据采集任务管理系统的主要API接口使用方法。通过合理使用这些接口，可以构建强大的数据采集和处理系统。

更多详细信息请参考：
- [安装配置](安装配置.md)
- [API文档](http://localhost:8000/docs)
