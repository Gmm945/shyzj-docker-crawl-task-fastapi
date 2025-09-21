#!/usr/bin/env python3
"""
模拟API服务器 - 用于测试爬虫容器心跳功能
"""

from flask import Flask, request, jsonify
import json
import time
from datetime import datetime

app = Flask(__name__)

# 存储心跳数据
heartbeat_data = []
completion_data = []

@app.route('/api/v1/monitoring/heartbeat', methods=['POST'])
def heartbeat():
    """接收心跳请求"""
    data = request.get_json()
    heartbeat_data.append({
        'timestamp': datetime.now().isoformat(),
        'data': data
    })
    print(f"收到心跳: {data.get('execution_id')} - 进度: {data.get('progress', {}).get('percentage', 0):.1f}%")
    return jsonify({"status": "success", "message": "心跳接收成功"})

@app.route('/api/v1/monitoring/completion', methods=['POST'])
def completion():
    """接收任务完成通知"""
    data = request.get_json()
    completion_data.append({
        'timestamp': datetime.now().isoformat(),
        'data': data
    })
    print(f"收到完成通知: {data.get('execution_id')} - 成功: {data.get('success')}")
    return jsonify({"status": "success", "message": "完成通知接收成功"})

@app.route('/api/v1/', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"message": "模拟API服务器运行正常", "status": "healthy"})

@app.route('/api/v1/monitoring/heartbeats', methods=['GET'])
def get_heartbeats():
    """获取所有心跳数据"""
    return jsonify({"heartbeats": heartbeat_data})

@app.route('/api/v1/monitoring/completions', methods=['GET'])
def get_completions():
    """获取所有完成通知"""
    return jsonify({"completions": completion_data})

if __name__ == '__main__':
    print("启动模拟API服务器...")
    print("心跳接口: http://localhost:8000/api/v1/monitoring/heartbeat")
    print("完成接口: http://localhost:8000/api/v1/monitoring/completion")
    print("健康检查: http://localhost:8000/api/v1/")
    app.run(host='0.0.0.0', port=8000, debug=True)
