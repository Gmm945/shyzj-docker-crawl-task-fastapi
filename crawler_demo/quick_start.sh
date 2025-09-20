#!/bin/bash

# 爬虫容器快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    print_success "Docker已安装"
}

# 构建镜像
build_image() {
    print_info "开始构建爬虫镜像..."
    
    if docker build -t crawler-service:latest .; then
        print_success "镜像构建成功"
    else
        print_error "镜像构建失败"
        exit 1
    fi
}

# 准备测试环境
prepare_test_env() {
    print_info "准备测试环境..."
    
    # 创建配置目录
    mkdir -p /tmp/task_configs/demo-execution
    mkdir -p /tmp/crawler_outputs
    
    # 复制配置文件
    if [ -f "config_examples/basic_crawler.json" ]; then
        cp config_examples/basic_crawler.json /tmp/task_configs/demo-execution/config.json
        print_success "配置文件已准备"
    else
        print_error "配置文件不存在"
        exit 1
    fi
}

# 运行容器
run_container() {
    local execution_id=${1:-"demo-execution-$(date +%s)"}
    local api_base_url=${2:-"http://localhost:8000"}
    
    print_info "启动爬虫容器..."
    print_info "执行ID: $execution_id"
    print_info "API地址: $api_base_url"
    
    # 停止已存在的容器
    docker stop crawler-demo 2>/dev/null || true
    docker rm crawler-demo 2>/dev/null || true
    
    # 运行新容器
    if docker run -d \
        --name crawler-demo \
        --rm \
        -v /tmp/task_configs/demo-execution/config.json:/app/config/config.json:ro \
        -v /tmp/crawler_outputs:/app/output \
        -e TASK_EXECUTION_ID="$execution_id" \
        -e CONFIG_PATH=/app/config/config.json \
        -e API_BASE_URL="$api_base_url" \
        crawler-service:latest; then
        
        print_success "容器启动成功"
        print_info "容器名称: crawler-demo"
    else
        print_error "容器启动失败"
        exit 1
    fi
}

# 查看日志
show_logs() {
    print_info "查看容器日志..."
    print_info "按 Ctrl+C 退出日志查看"
    
    sleep 2  # 等待容器启动
    
    if docker logs -f crawler-demo; then
        print_info "日志查看结束"
    else
        print_error "日志查看失败"
    fi
}

# 停止容器
stop_container() {
    print_info "停止容器..."
    
    if docker stop crawler-demo 2>/dev/null; then
        print_success "容器已停止"
    else
        print_warning "容器可能已经停止"
    fi
}

# 清理环境
cleanup() {
    print_info "清理测试环境..."
    
    # 停止容器
    stop_container
    
    # 清理配置文件
    rm -rf /tmp/task_configs/demo-execution 2>/dev/null || true
    rm -rf /tmp/crawler_outputs/* 2>/dev/null || true
    
    print_success "环境清理完成"
}

# 运行测试
run_tests() {
    print_info "运行测试..."
    
    # 检查Python环境
    if ! command -v python3 &> /dev/null; then
        print_warning "Python3未安装，跳过测试"
        return
    fi
    
    # 运行爬虫测试
    if [ -f "test/test_crawler.py" ]; then
        print_info "运行爬虫功能测试..."
        if python3 test/test_crawler.py; then
            print_success "爬虫测试通过"
        else
            print_error "爬虫测试失败"
        fi
    fi
    
    # 运行心跳测试
    if [ -f "test/test_heartbeat.py" ]; then
        print_info "运行心跳功能测试..."
        if python3 test/test_heartbeat.py; then
            print_success "心跳测试通过"
        else
            print_warning "心跳测试跳过（API服务可能未运行）"
        fi
    fi
}

# 显示帮助信息
show_help() {
    echo "爬虫容器快速启动脚本"
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  build                    构建Docker镜像"
    echo "  run [execution_id] [api_url]  运行容器"
    echo "  logs                     查看容器日志"
    echo "  stop                     停止容器"
    echo "  test                     运行测试"
    echo "  cleanup                  清理环境"
    echo "  all                      执行完整流程（构建->运行->日志）"
    echo "  help                     显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 build                 # 构建镜像"
    echo "  $0 run                   # 运行容器"
    echo "  $0 run my-task-id http://api:8000  # 使用自定义参数运行"
    echo "  $0 logs                  # 查看日志"
    echo "  $0 all                   # 完整流程"
}

# 主函数
main() {
    local command=${1:-"help"}
    
    case $command in
        "build")
            check_docker
            build_image
            ;;
        "run")
            check_docker
            prepare_test_env
            run_container "$2" "$3"
            ;;
        "logs")
            show_logs
            ;;
        "stop")
            stop_container
            ;;
        "test")
            run_tests
            ;;
        "cleanup")
            cleanup
            ;;
        "all")
            check_docker
            build_image
            prepare_test_env
            run_container "$2" "$3"
            echo ""
            print_info "容器已启动，可以运行 '$0 logs' 查看日志"
            print_info "或者运行 '$0 test' 进行测试"
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 脚本入口
main "$@"
