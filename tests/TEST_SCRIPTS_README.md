# 数据采集任务管理系统 - 测试脚本说明

本文档介绍了系统中提供的测试脚本，用于验证各个功能模块是否正常工作。

## 📁 测试文件夹结构

```
tests/
├── __init__.py              # 测试包初始化文件
├── run_tests.py             # 测试运行器（推荐使用）
├── test_config.py           # 测试配置文件
├── test_utils.py            # 测试工具模块
├── simple_test.py           # 简化测试（推荐新手使用）
├── quick_test.py            # 快速基础测试
├── docker_test.py           # Docker功能测试
├── test_examples.py         # 完整功能测试
└── TEST_SCRIPTS_README.md   # 本文档
```

## 🚀 快速开始

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

### 传统方式：直接运行测试脚本
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

## 📁 测试脚本详细说明

### 1. `run_tests.py` - 测试运行器（推荐）
**功能**: 统一的测试入口，支持批量运行和结果汇总

**特性**:
- ✅ 统一的测试入口
- ✅ 批量测试运行
- ✅ 测试结果汇总
- ✅ 前置条件检查
- ✅ 灵活的测试选择

**使用方法**:
```bash
# 列出所有可用测试
python tests/run_tests.py --list

# 运行简化测试（推荐新手）
python tests/run_tests.py --simple

# 运行快速测试
python tests/run_tests.py --quick

# 运行Docker测试
python tests/run_tests.py --docker

# 运行完整测试
python tests/run_tests.py --full

# 运行所有测试
python tests/run_tests.py

# 检查前置条件
python tests/run_tests.py --check
```

### 2. `simple_test.py` - 简化测试（推荐新手使用）
**功能**: 简化的系统测试，适合新手快速验证系统功能

**测试内容**:
- ✅ 系统根路径响应
- ✅ 管理员账户初始化
- ✅ 管理员登录
- ✅ 用户创建
- ✅ 任务创建
- ✅ 任务列表获取
- ✅ 测试数据清理

**使用方法**:
```bash
python tests/simple_test.py
```

### 3. `quick_test.py` - 快速基础测试
**功能**: 简化的快速测试，验证系统基本功能

**测试内容**:
- ✅ 系统根路径响应
- ✅ API文档可访问性
- ✅ 用户注册和登录
- ✅ 任务创建
- ✅ 任务列表获取
- ✅ 测试数据清理

**使用方法**:
```bash
python tests/quick_test.py
```

### 4. `docker_test.py` - Docker功能测试
**功能**: 专门测试Docker容器管理相关功能

**测试内容**:
- ✅ Docker健康检查
- ✅ 容器状态监控
- ✅ 容器日志获取
- ✅ Docker任务执行
- ✅ 容器管理功能

**使用方法**:
```bash
python tests/docker_test.py
```

### 5. `test_examples.py` - 完整功能测试
**功能**: 全面的系统功能测试，包含所有主要功能模块

**测试内容**:
- ✅ 系统健康检查
- ✅ 用户注册和认证
- ✅ 任务创建和管理
- ✅ 任务调度功能
- ✅ 任务执行监控
- ✅ 系统监控功能
- ✅ 数据清理

**使用方法**:
```bash
python tests/test_examples.py
```

### 6. `test_config.py` - 测试配置文件
**功能**: 集中管理测试配置参数

**包含内容**:
- ✅ 服务器地址和端口配置
- ✅ 测试用户信息配置
- ✅ 测试任务配置模板
- ✅ 调度配置模板
- ✅ 测试数据配置
- ✅ 日志配置

### 7. `test_utils.py` - 测试工具模块
**功能**: 提供测试脚本中常用的工具函数

**包含内容**:
- ✅ HTTP客户端封装
- ✅ 认证管理器
- ✅ 测试数据管理器
- ✅ 结果验证工具
- ✅ 测试辅助工具

### 8. `comprehensive_api_test.py` - 全面API接口测试
**功能**: 测试系统中的所有API接口，提供最全面的接口覆盖测试

**测试内容**:
- ✅ 通用接口测试 (系统根路径、健康检查、存活检查、就绪检查、系统统计)
- ✅ 用户管理接口测试 (用户创建、列表、详情、更新、删除、状态切换)
- ✅ 认证接口测试 (登录、登出、密码修改、用户信息获取)
- ✅ 任务管理接口测试 (任务创建、列表、详情、更新、执行、停止)
- ✅ 调度器接口测试 (调度创建、列表、状态切换、删除)
- ✅ 监控接口测试 (心跳、完成通知、执行状态、统计信息)
- ✅ 测试数据清理

**使用方法**:
```bash
python tests/comprehensive_api_test.py
# 或使用测试运行器
python tests/run_tests.py --comprehensive
```

**特性**:
- 🎯 全面的接口覆盖测试
- 📊 详细的测试报告生成
- 🧹 自动测试数据清理
- 📈 测试结果统计和分析
- 💾 测试报告保存到JSON文件

## 🚀 运行前准备

### 1. 确保服务正在运行
在运行测试脚本之前，请确保以下服务已经启动：

```bash
# 启动MySQL数据库
docker-compose -f docker/docker-compose.mysql.yml up -d

# 启动Redis (如果使用Docker)
docker run -d --name redis -p 6379:6379 redis:5.0.14

# 启动主服务
pdm run start
```

### 2. 检查服务状态
```bash
# 检查MySQL容器
docker ps | grep mysql

# 检查Redis容器
docker ps | grep redis

# 检查主服务
curl http://localhost:8000/api/v1/
```

### 3. 安装测试依赖
测试脚本使用以下Python包，请确保已安装：

```bash
# 使用PDM安装（推荐）
pdm install

# 或使用pip安装
pip install httpx loguru
```

### 4. 检查测试环境
```bash
# 检查前置条件
python tests/run_tests.py --check

# 或手动检查服务器状态
curl http://localhost:8000/api/v1/
```

## 📊 测试结果说明

### 成功输出示例
```
🚀 开始运行数据采集任务管理系统测试...
🔍 测试系统健康状态...
✅ 系统根路径响应: {'message': '数据采集任务管理系统', 'data': {'version': '1.0.0'}}
✅ Redis健康检查: {'status': 'healthy'}
👤 测试用户管理功能...
📝 注册用户: test_user_1695123456
✅ 用户注册成功: {'id': 'abc123...', 'username': 'test_user_1695123456'}
...
📊 测试结果: 7/7 通过
🎉 所有测试通过！系统运行正常！
```

### 失败输出示例
```
❌ 系统健康检查失败: HTTP 500 Error
⚠️ 3 个测试失败
❌ 测试完成！部分功能存在问题！
```

## 🔧 自定义测试

### 修改测试参数
你可以通过修改配置文件来自定义测试参数：

1. **修改服务器地址**:
```python
# 修改 tests/test_config.py 中的配置
BASE_URL: str = "http://your-server:8000"
```

2. **修改测试用户信息**:
```python
# 修改 tests/test_config.py 中的配置
TEST_USER_PREFIX: str = "your_test_user"
TEST_USER_PASSWORD: str = "YourPassword123!"
```

3. **修改测试任务配置**:
```python
# 修改 tests/test_config.py 中的 TEST_TASK_CONFIGS
TEST_TASK_CONFIGS = {
    "custom_task": {
        "task_type": "api",
        "base_url": "https://your-target-site.com",
        # ... 其他配置
    }
}
```

4. **使用环境变量**:
```bash
# 设置环境变量来覆盖配置
export TEST_BASE_URL="http://your-server:8000"
export TEST_ADMIN_PASSWORD="your_admin_password"
```

### 添加新的测试用例
你可以基于现有脚本添加新的测试用例：

1. **创建新的测试脚本**:
```python
# tests/my_custom_test.py
import asyncio
from tests.test_utils import TestHTTPClient, AuthManager, TestDataManager

async def test_my_feature():
    """测试我的功能"""
    async with TestHTTPClient() as client:
        auth_manager = AuthManager(client)
        data_manager = TestDataManager(client)
        
        # 初始化管理员并登录
        await auth_manager.init_admin()
        await auth_manager.login_admin()
        
        # 你的测试逻辑
        response = await client.get("/api/v1/your-endpoint")
        logger.success(f"✅ 我的功能测试成功: {response.json()}")
        
        # 清理测试数据
        await data_manager.cleanup_all()

async def main():
    await test_my_feature()

if __name__ == "__main__":
    asyncio.run(main())
```

2. **添加到测试运行器**:
```python
# 修改 tests/run_tests.py 中的 test_scripts 字典
self.test_scripts = {
    "simple": "simple_test.py",
    "quick": "quick_test.py", 
    "docker": "docker_test.py",
    "full": "test_examples.py",
    "custom": "my_custom_test.py"  # 添加你的测试
}
```

## 🐛 故障排除

### 常见问题

1. **连接被拒绝**
   - 检查服务是否正在运行
   - 检查端口是否正确（默认8000）
   - 检查防火墙设置

2. **认证失败**
   - 检查用户注册是否成功
   - 检查密码是否正确
   - 检查token是否有效

3. **数据库错误**
   - 检查MySQL是否正在运行
   - 检查数据库连接配置
   - 检查数据库迁移是否完成

4. **Docker相关错误**
   - 检查Docker是否正在运行
   - 检查Docker API访问权限
   - 检查容器状态

### 调试模式
启用详细日志输出：

```python
# 在脚本中添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 测试报告

测试完成后，你可以：

1. **保存测试日志**:
```bash
# 保存单个测试的日志
python tests/simple_test.py > tests/test_results.log 2>&1

# 保存测试运行器的日志
python tests/run_tests.py > tests/run_results.log 2>&1
```

2. **生成测试报告**:
可以基于测试结果生成HTML或JSON格式的测试报告

3. **集成到CI/CD**:
将测试脚本集成到你的持续集成流程中

## 🤝 贡献

如果你发现测试脚本的问题或有改进建议，请：

1. 提交Issue描述问题
2. 提交Pull Request提供修复
3. 添加新的测试用例

## 📞 支持

如果遇到问题，请：

1. 查看系统日志
2. 检查服务状态
3. 参考项目文档
4. 提交Issue寻求帮助

---

**注意**: 测试脚本会创建和删除测试数据，请确保在测试环境中运行，避免影响生产数据。
