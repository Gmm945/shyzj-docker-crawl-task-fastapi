#!/usr/bin/env python3
"""
爬虫任务容器服务 - 符合数据采集任务管理系统规范
专门用于在Docker容器中执行爬虫任务，保持心跳机制

环境变量要求：
- TASK_EXECUTION_ID: 任务执行ID（UUID格式）
- CONFIG_PATH: 配置文件路径
- API_BASE_URL: 主控系统API地址（可选，默认http://localhost:8000）
"""

import os
import json
import time
import threading
import signal
import sys
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import logging
from requests.adapters import HTTPAdapter
try:
    # urllib3 v2
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    from urllib3.util import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CrawlProgress:
    """爬虫进度信息"""
    total_urls: int = 0
    crawled_urls: int = 0
    successful_urls: int = 0
    failed_urls: int = 0
    current_url: str = ""
    current_stage: str = "初始化"
    start_time: Optional[datetime] = None
    data_items: int = 0
    error_count: int = 0

class SimpleCrawler:
    """简单爬虫实现"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.progress = CrawlProgress()
        self.is_running = False
        self.should_stop = False
        self.results = []
        
        # 配置请求会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.get('user_agent', 'Mozilla/5.0 (compatible; DataCollector/1.0)')
        })
        # 配置重试（对 5xx/429/连接错误做指数退避重试）
        retry_total = int(os.getenv('CRAWLER_RETRY_TOTAL', self.config.get('retry_total', 3)))
        backoff = float(os.getenv('CRAWLER_RETRY_BACKOFF', self.config.get('retry_backoff', 1)))
        status_list = [429, 500, 502, 503, 504]
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            backoff_factor=backoff,
            status_forcelist=status_list,
            allowed_methods={"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.timeout = self.config.get('timeout', 30)
        self.delay = self.config.get('delay', 1)
        
    def start(self):
        """启动爬虫任务"""
        logger.info(f"启动爬虫任务: {self.config['task_name']}")
        self.is_running = True
        self.progress.start_time = datetime.now()
        
        try:
            self._crawl_targets()
        except Exception as e:
            logger.error(f"爬虫任务异常: {e}")
            self.progress.current_stage = f"错误: {str(e)}"
            self.progress.error_count += 1
        finally:
            self.is_running = False
            logger.info("爬虫任务结束")
    
    def _crawl_targets(self):
        """爬取目标URL列表"""
        base_url = self.config['base_url']
        target_urls = self.config.get('target_urls', [base_url])
        
        if base_url not in target_urls:
            target_urls.insert(0, base_url)
        
        self.progress.total_urls = len(target_urls)
        self.progress.current_stage = "开始爬取"
        
        for i, url in enumerate(target_urls):
            if self.should_stop:
                logger.info("收到停止信号，退出爬取")
                break
                
            self.progress.current_url = url
            self.progress.current_stage = f"爬取中 ({i+1}/{self.progress.total_urls})"
            
            try:
                success = self._crawl_single_url(url)
                if success:
                    self.progress.successful_urls += 1
                else:
                    self.progress.failed_urls += 1
                    
                self.progress.crawled_urls += 1
                
                if self.delay > 0:
                    time.sleep(self.delay)
                    
            except Exception as e:
                logger.error(f"爬取URL失败 {url}: {e}")
                self.progress.failed_urls += 1
                self.progress.crawled_urls += 1
                self.progress.error_count += 1
        
        self.progress.current_stage = "爬取完成"
    
    def _crawl_single_url(self, url: str) -> bool:
        """爬取单个URL"""
        try:
            logger.info(f"爬取URL: {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # 简单的数据提取
            data = {
                'url': url,
                'status_code': response.status_code,
                'content_length': len(response.text),
                'timestamp': datetime.now().isoformat(),
                'title': self._extract_title(response.text),
                'links': self._extract_links(response.text, url)
            }
            
            self.results.append(data)
            self.progress.data_items += 1
            
            logger.info(f"从 {url} 提取了数据")
            return True
            
        except requests.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"处理失败 {url}: {e}")
            return False
    
    def _extract_title(self, content: str) -> str:
        """提取页面标题"""
        try:
            import re
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
        except:
            pass
        return "无标题"
    
    def _extract_links(self, content: str, base_url: str) -> List[str]:
        """提取页面链接"""
        try:
            from urllib.parse import urljoin
            import re
            
            # 简单的链接提取
            link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
            links = re.findall(link_pattern, content, re.IGNORECASE)
            
            # 转换为绝对URL
            absolute_links = []
            for link in links[:10]:  # 限制数量
                absolute_link = urljoin(base_url, link)
                absolute_links.append(absolute_link)
            
            return absolute_links
        except:
            return []
    
    def stop(self):
        """停止爬虫任务"""
        self.should_stop = True
        logger.info("正在停止爬虫任务...")
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度"""
        progress_dict = asdict(self.progress)
        
        # 计算百分比
        if self.progress.total_urls > 0:
            progress_dict['percentage'] = round(
                self.progress.crawled_urls / self.progress.total_urls * 100, 2
            )
        else:
            progress_dict['percentage'] = 0
        
        # 计算运行时间
        if self.progress.start_time:
            runtime = datetime.now() - self.progress.start_time
            progress_dict['runtime_seconds'] = runtime.total_seconds()
        
        # 转换datetime对象为字符串
        if 'start_time' in progress_dict and progress_dict['start_time']:
            progress_dict['start_time'] = progress_dict['start_time'].isoformat()
        
        return progress_dict

class HeartbeatClient:
    """心跳客户端"""
    
    def __init__(self, api_base_url: str, execution_id: str, container_name: str):
        self.api_base_url = api_base_url.rstrip('/')
        self.execution_id = execution_id
        self.container_name = container_name
        self.heartbeat_url = f"{self.api_base_url}/api/v1/monitoring/heartbeat"
        self.completion_url = f"{self.api_base_url}/api/v1/monitoring/completion"
        
    def send_heartbeat(self, crawler: SimpleCrawler):
        """发送心跳"""
        try:
            progress = crawler.get_progress()
            
            heartbeat_data = {
                "execution_id": self.execution_id,
                "container_name": self.container_name,
                "status": "running" if crawler.is_running else "completed",
                "progress": progress,
                "timestamp": int(time.time())
            }
            
            response = requests.post(
                self.heartbeat_url,
                json=heartbeat_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.debug(f"心跳发送成功: {progress['percentage']:.1f}%")
            else:
                logger.warning(f"心跳请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"心跳发送异常: {e}")
    
    def send_completion(self, crawler: SimpleCrawler, success: bool, error_message: Optional[str] = None):
        """发送任务完成通知"""
        try:
            progress = crawler.get_progress()
            
            completion_data = {
                "execution_id": self.execution_id,
                "container_name": self.container_name,
                "success": success,
                "result_data": {
                    "crawl_summary": progress,
                    "data_items": crawler.results[:50],  # 只返回前50条数据
                    "total_data_count": len(crawler.results)
                },
                "error_message": error_message
            }
            
            response = requests.post(
                self.completion_url,
                json=completion_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info("任务完成通知发送成功")
            else:
                try:
                    logger.warning(f"任务完成通知发送失败: {response.status_code}, body={response.text}")
                except Exception:
                    logger.warning(f"任务完成通知发送失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"发送任务完成通知异常: {e}")

class CrawlerContainerService:
    """爬虫容器服务"""
    
    def __init__(self):
        # 从环境变量获取配置
        self.execution_id = os.getenv('TASK_EXECUTION_ID')
        self.container_name = os.getenv('HOSTNAME', 'crawler-container')
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.config_path = os.getenv('CONFIG_PATH', '/app/config/config.json')
        
        if not self.execution_id:
            raise ValueError("未设置 TASK_EXECUTION_ID 环境变量")
        
        # 加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # 初始化组件
        self.crawler = SimpleCrawler(self.config)
        self.heartbeat_client = HeartbeatClient(self.api_base_url, self.execution_id, self.container_name)
        
        # 设置信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info(f"爬虫容器服务初始化完成 - 执行ID: {self.execution_id}")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，正在优雅关闭...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """启动服务"""
        logger.info(f"启动爬虫容器服务 - 执行ID: {self.execution_id}")
        
        try:
            # 启动爬虫任务（在独立线程中）
            crawler_thread = threading.Thread(target=self._run_crawler_with_heartbeat, daemon=True)
            crawler_thread.start()
            
            # 等待爬虫任务完成
            crawler_thread.join()
            
            # 发送完成通知
            success = self.crawler.progress.error_count == 0
            error_message = None if success else "爬虫任务执行过程中出现错误"
            
            self.heartbeat_client.send_completion(self.crawler, success, error_message)
            
            logger.info("爬虫容器服务结束")
            
        except Exception as e:
            logger.error(f"服务启动失败: {e}")
            self.heartbeat_client.send_completion(self.crawler, False, str(e))
    
    def _run_crawler_with_heartbeat(self):
        """运行爬虫任务并定期发送心跳"""
        try:
            # 启动爬虫任务
            crawler_thread = threading.Thread(target=self.crawler.start, daemon=True)
            crawler_thread.start()
            
            # 定期发送心跳
            while self.crawler.is_running and not self.crawler.should_stop:
                self.heartbeat_client.send_heartbeat(self.crawler)
                time.sleep(30)  # 每30秒发送一次心跳
            
            # 等待爬虫任务完成
            crawler_thread.join()
            
        except Exception as e:
            logger.error(f"爬虫任务执行异常: {e}")
            self.heartbeat_client.send_completion(
                self.crawler, 
                False, 
                f"爬虫任务执行异常: {str(e)}"
            )
    
    def stop(self):
        """停止服务"""
        logger.info("正在停止爬虫容器服务...")
        self.crawler.stop()

def main():
    """主函数"""
    try:
        service = CrawlerContainerService()
        service.start()
        return 0
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
