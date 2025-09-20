# 数据采集任务管理系统 - 测试指南

本文档提供了系统测试的快速指南。

## 🚀 快速测试

### 推荐方式：使用测试运行器
```bash
# 列出所有可用测试
python tests/run_tests.py --list

# 运行简化测试（推荐新手）
python tests/run_tests.py --simple

# 运行所有测试
python tests/run_tests.py

# 检查前置条件
python tests/run_tests.py --check
```

### 直接运行测试脚本
```bash
# 运行简化测试
python tests/simple_test.py

# 运行快速测试
python tests/quick_test.py

# 运行Docker测试
python tests/docker_test.py

# 运行完整测试
python tests/test_examples.py

# 运行全面API测试
python tests/comprehensive_api_test.py
```

## 📁 测试文件夹结构

```
tests/
├── run_tests.py             # 测试运行器（推荐使用）
├── simple_test.py           # 简化测试（推荐新手使用）
├── quick_test.py            # 快速基础测试
├── docker_test.py           # Docker功能测试
├── test_examples.py         # 完整功能测试
├── comprehensive_api_test.py # 全面API接口测试
├── test_config.py           # 测试配置文件
├── test_utils.py            # 测试工具模块
└── TEST_SCRIPTS_README.md   # 详细文档
```

## 🔧 运行前准备

1. **确保服务正在运行**:
```bash
# 启动MySQL数据库
docker-compose -f docker/docker-compose.mysql.yml up -d

# 启动Redis (如果使用Docker)
docker run -d --name redis -p 6379:6379 redis:5.0.14

# 启动主服务
pdm run start
```

2. **检查服务状态**:
```bash
# 检查服务器是否运行
curl http://localhost:8000/api/v1/

# 或使用测试运行器检查
python tests/run_tests.py --check
```

3. **安装依赖**:
```bash
# 使用PDM安装（推荐）
pdm install

# 或使用pip安装
pip install httpx loguru
```

## 📊 测试类型说明

| 测试类型 | 文件名 | 适用场景 | 预计时间 |
|---------|--------|----------|----------|
| 简化测试 | `simple_test.py` | 新手验证基本功能 | 1-2分钟 |
| 快速测试 | `quick_test.py` | 日常功能验证 | 30秒 |
| Docker测试 | `docker_test.py` | Docker功能验证 | 2-3分钟 |
| 完整测试 | `test_examples.py` | 全面功能测试 | 5-10分钟 |
| 全面API测试 | `comprehensive_api_test.py` | 所有API接口测试 | 1-2分钟 |

## 🎯 测试内容概览

### 简化测试 (simple_test.py)
- ✅ 系统根路径响应
- ✅ 管理员账户初始化
- ✅ 管理员登录
- ✅ 用户创建
- ✅ 任务创建
- ✅ 任务列表获取
- ✅ 测试数据清理

### 快速测试 (quick_test.py)
- ✅ 系统根路径响应
- ✅ API文档可访问性
- ✅ 用户注册和登录
- ✅ 任务创建
- ✅ 任务列表获取
- ✅ 测试数据清理

### Docker测试 (docker_test.py)
- ✅ Docker健康检查
- ✅ 容器状态监控
- ✅ 容器日志获取
- ✅ Docker任务执行
- ✅ 容器管理功能

### 完整测试 (test_examples.py)
- ✅ 系统健康检查
- ✅ 用户注册和认证
- ✅ 任务创建和管理
- ✅ 任务调度功能
- ✅ 任务执行监控
- ✅ 系统监控功能
- ✅ 数据清理

### 全面API测试 (comprehensive_api_test.py)
- ✅ 通用接口测试 (系统根路径、健康检查、存活检查、就绪检查、系统统计)
- ✅ 用户管理接口测试 (用户创建、列表、详情、更新、删除、状态切换)
- ✅ 认证接口测试 (登录、登出、密码修改、用户信息获取)
- ✅ 任务管理接口测试 (任务创建、列表、详情、更新、执行、停止)
- ✅ 调度器接口测试 (调度创建、列表、状态切换、删除)
- ✅ 监控接口测试 (心跳、完成通知、执行状态、统计信息)
- ✅ 测试数据清理

## 🔧 自定义测试

### 修改配置
编辑 `tests/test_config.py` 文件来自定义测试参数：

```python
# 修改服务器地址
BASE_URL: str = "http://your-server:8000"

# 修改管理员密码
ADMIN_PASSWORD: str = "your_admin_password"

# 修改测试用户前缀
TEST_USER_PREFIX: str = "your_test_user"
```

### 使用环境变量
```bash
export TEST_BASE_URL="http://your-server:8000"
export TEST_ADMIN_PASSWORD="your_admin_password"
```

## 🐛 故障排除

### 常见问题

1. **连接被拒绝**
   - 检查服务是否正在运行
   - 检查端口是否正确（默认8000）
   - 检查防火墙设置

2. **认证失败**
   - 检查管理员账户是否正确初始化
   - 检查密码是否正确
   - 运行 `python tests/run_tests.py --check` 检查

3. **数据库错误**
   - 检查MySQL是否正在运行
   - 检查数据库连接配置
   - 检查数据库迁移是否完成

4. **Docker相关错误**
   - 检查Docker是否正在运行
   - 检查Docker API访问权限
   - 检查容器状态

### 获取帮助

1. 查看详细文档：`tests/TEST_SCRIPTS_README.md`
2. 运行前置条件检查：`python tests/run_tests.py --check`
3. 查看系统日志
4. 提交Issue寻求帮助

## 📝 测试报告

### 保存测试日志
```bash
# 保存测试运行器的日志
python tests/run_tests.py > tests/run_results.log 2>&1

# 保存单个测试的日志
python tests/simple_test.py > tests/simple_results.log 2>&1
```

### 集成到CI/CD
可以将测试脚本集成到你的持续集成流程中：

```yaml
# GitHub Actions 示例
- name: Run Tests
  run: |
    python tests/run_tests.py --simple
```

---

**注意**: 测试脚本会创建和删除测试数据，请确保在测试环境中运行，避免影响生产数据。
