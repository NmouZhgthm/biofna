import sys
import os
import time
import traceback
import psutil
import gc
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QSpinBox, QTextEdit, QMessageBox, QCheckBox,
                             QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QIcon, QFont
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class BrowserWorker(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, video_url, watch_time, headless=False, show_window=True, max_retries=3, thread_id=1):
        super().__init__()
        self.video_url = video_url
        self.watch_time = watch_time
        self.headless = headless
        self.show_window = show_window
        self.max_retries = max_retries
        self.thread_id = thread_id
        self.is_running = True
        self.memory_check_interval = 5  # 内存检查间隔（秒）- 优化为更频繁检查
        self.max_memory_mb = 400  # 降低最大内存使用限制（MB）
        self.last_gc_time = time.time()  # 上次垃圾回收时间
        
    def check_memory_usage(self, pid):
        """检查指定进程的内存使用情况，如果超过阈值则返回True"""
        try:
            if pid is None:
                return False
                
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024  # 转换为MB
            
            self.update_signal.emit(f"[线程{self.thread_id}] 当前内存使用: {memory_mb:.2f} MB")
            
            if memory_mb > self.max_memory_mb:
                self.update_signal.emit(f"[线程{self.thread_id}] 警告: 内存使用超过阈值 ({memory_mb:.2f} MB > {self.max_memory_mb} MB)")
                return True
            return False
        except Exception as e:
            self.update_signal.emit(f"[线程{self.thread_id}] 检查内存时出错: {str(e)}")
            return False
    
    def run(self):
        driver = None
        retry_count = 0
        browser_pid = None  # 存储浏览器进程ID
        last_memory_cleanup = time.time()  # 记录上次内存清理时间
        
        while retry_count < self.max_retries and self.is_running:
            try:
                self.update_signal.emit(f"[线程{self.thread_id}] 正在启动浏览器...")
                
                # 配置Chrome选项 - 优化内存占用
                chrome_options = Options()
                chrome_options.add_argument("--incognito")  # 无痕模式
                chrome_options.add_argument("--mute-audio")  # 静音
                chrome_options.add_argument("--disable-extensions")  # 禁用扩展
                chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
                chrome_options.add_argument("--no-sandbox")  # 禁用沙盒模式
                chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用
                
                # 内存优化选项
                chrome_options.add_argument("--js-flags=--expose-gc")  # 允许手动垃圾回收
                chrome_options.add_argument("--single-process")  # 单进程模式
                chrome_options.add_argument("--disable-application-cache")  # 禁用应用缓存
                chrome_options.add_argument("--disable-infobars")  # 禁用信息栏
                chrome_options.add_argument("--disable-notifications")  # 禁用通知
                chrome_options.add_argument("--disable-popup-blocking")  # 禁用弹窗
                chrome_options.add_argument("--disable-save-password-bubble")  # 禁用保存密码
                chrome_options.add_argument("--disable-translate")  # 禁用翻译
                chrome_options.add_argument("--disable-web-security")  # 禁用网页安全
                chrome_options.add_argument("--disable-client-side-phishing-detection")  # 禁用钓鱼检测
                chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # 禁用图片加载
                chrome_options.add_argument("--disable-default-apps")  # 禁用默认应用
                
                # 设置内存限制
                chrome_options.add_argument("--memory-pressure-off")  # 关闭内存压力检测
                chrome_options.add_argument("--aggressive-cache-discard")  # 积极丢弃缓存
                chrome_options.add_argument("--disable-features=site-per-process")  # 禁用每个站点一个进程
                
                if self.headless:
                    chrome_options.add_argument("--headless=new")  # 无头模式
                
                # 控制窗口显示
                if not self.show_window and not self.headless:
                    # 将窗口移到屏幕外或最小化
                    chrome_options.add_argument("--window-position=0,0")
                    chrome_options.add_argument("--window-size=1,1")
                
                # 使用本地ChromeDriver
                chrome_driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                                "chromedriver-win64", "chromedriver.exe")
                
                if os.path.exists(chrome_driver_path):
                    self.update_signal.emit(f"[线程{self.thread_id}] 使用本地ChromeDriver")
                    service = Service(executable_path=chrome_driver_path)
                else:
                    self.update_signal.emit(f"[线程{self.thread_id}] 本地ChromeDriver不存在，尝试自动下载...")
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                
                # 启动浏览器
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.set_page_load_timeout(30)  # 设置页面加载超时时间
                
                # 设置脚本超时时间，减少长时间运行脚本导致的内存泄漏
                driver.set_script_timeout(20)
                
                # 获取浏览器进程ID用于内存监控
                try:
                    browser_pid = driver.service.process.pid
                    self.update_signal.emit(f"[线程{self.thread_id}] 浏览器进程ID: {browser_pid}")
                except Exception as e:
                    browser_pid = None
                    self.update_signal.emit(f"[线程{self.thread_id}] 无法获取浏览器进程ID: {str(e)}")
                
                # 打开视频前清理内存
                self.update_signal.emit(f"[线程{self.thread_id}] 正在打开视频: {self.video_url}")
                
                # 使用低内存模式打开页面
                driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": [
                    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.svg", 
                    "*.woff", "*.woff2", "*.ttf", "*.otf",
                    "*analytics*", "*tracking*", "*advertisement*"
                ]})
                driver.execute_cdp_cmd('Network.enable', {})
                
                # 打开视频
                driver.get(self.video_url)
                
                # 等待页面加载完成
                self.update_signal.emit(f"[线程{self.thread_id}] 等待页面加载...")
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "video"))
                    )
                    self.update_signal.emit(f"[线程{self.thread_id}] 视频元素已加载")
                except TimeoutException:
                    self.update_signal.emit(f"[线程{self.thread_id}] 未检测到视频元素，但将继续执行")
                
                # 观看视频
                self.update_signal.emit(f"[线程{self.thread_id}] 正在观看视频，将在 {self.watch_time} 秒后关闭...")
                
                # 优化视频播放，减少内存占用
                try:
                    # 暂停不必要的网络活动
                    driver.execute_script("""
                    if (window.performance && window.performance.memory) {
                        console.log('内存使用情况:', window.performance.memory.usedJSHeapSize / 1048576, 'MB');
                    }
                    
                    // 禁用动画和过渡效果
                    document.body.style.setProperty('--transition-duration', '0s', 'important');
                    const styleElement = document.createElement('style');
                    styleElement.textContent = '* { animation-duration: 0s !important; transition-duration: 0s !important; }';
                    document.head.appendChild(styleElement);
                    """)
                    
                    # 禁用不必要的元素和优化DOM
                    driver.execute_script("""
                    // 移除不必要的DOM元素
                    const nonEssentialSelectors = [
                        '.comment-container', '.recommend-container', 
                        '.video-toolbar', '.up-info', '.video-desc', 
                        '.video-sections', '.activity-m', '.report-wrap-module',
                        '.bilibili-player-video-danmaku', '.bilibili-player-video-subtitle',
                        '.bilibili-player-video-control-wrap', '.bilibili-player-video-control-bottom-center',
                        '.bpx-player-sending-area', '.bpx-player-dialog-area',
                        'iframe', '.ad-report', '.pop-live-small-mode'
                    ];
                    
                    // 使用更高效的DOM操作方式
                    const removeElements = (selector) => {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length === 0) return;
                        
                        // 创建文档片段进行批量操作
                        const fragment = document.createDocumentFragment();
                        elements.forEach(el => {
                            if (el && el.parentNode) {
                                el.parentNode.removeChild(el);
                            }
                        });
                    };
                    
                    // 批量处理元素移除
                    nonEssentialSelectors.forEach(selector => removeElements(selector));
                    
                    // 限制视频质量，降低资源占用
                    const videoElement = document.querySelector('video');
                    if (videoElement) {
                        videoElement.setAttribute('preload', 'metadata');
                        videoElement.volume = 0;
                        videoElement.playbackRate = 1.0;
                        
                        // 如果有高清视频，降低分辨率
                        if (videoElement.videoHeight > 720) {
                            videoElement.style.maxHeight = '720px';
                        }
                    }
                    """)
                except Exception as e:
                    self.update_signal.emit(f"[线程{self.thread_id}] 优化视频播放时出错: {str(e)}")
                
                # 倒计时，并定期清理内存
                for i in range(self.watch_time, 0, -1):
                    if not self.is_running:
                        break
                    
                    # 每10秒检查一次内存使用情况
                    if i % self.memory_check_interval == 0 and browser_pid:
                        if self.check_memory_usage(browser_pid):
                            # 内存使用超过阈值，执行紧急内存清理
                            self.update_signal.emit(f"[线程{self.thread_id}] 执行紧急内存清理...")
                            try:
                                # 关闭不必要的标签页
                                if len(driver.window_handles) > 1:
                                    current = driver.current_window_handle
                                    for handle in driver.window_handles:
                                        if handle != current:
                                            driver.switch_to.window(handle)
                                            driver.close()
                                    driver.switch_to.window(current)
                                
                                # 清理页面资源
                                driver.execute_script("""
                                // 移除所有iframe
                                const iframes = document.querySelectorAll('iframe');
                                iframes.forEach(iframe => iframe.remove());
                                
                                // 移除大型图片和视频元素
                                const largeMedia = document.querySelectorAll('img[src], video');
                                largeMedia.forEach(media => {
                                    if (!isElementInViewport(media)) {
                                        media.remove();
                                    }
                                });
                                
                                // 清除事件监听器
                                const allElements = document.querySelectorAll('*');
                                allElements.forEach(el => {
                                    el.onclick = null;
                                    el.onmouseover = null;
                                    el.onmouseout = null;
                                });
                                
                                function isElementInViewport(el) {
                                    const rect = el.getBoundingClientRect();
                                    return (
                                        rect.top >= 0 &&
                                        rect.left >= 0 &&
                                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                                        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                                    );
                                }
                                """)
                                
                                # 强制垃圾回收 - 优化版本
                                gc.collect(2)  # 使用完整收集模式
                                driver.execute_script("window.gc();")  # 浏览器端垃圾回收
                                
                                # 清理Python内部缓存
                                import sys
                                if hasattr(sys, 'getsizeof'):
                                    for obj in gc.get_objects():
                                        if hasattr(obj, '__class__') and sys.getsizeof(obj) > 1024*1024:  # 大于1MB的对象
                                            try:
                                                del obj
                                            except:
                                                pass
                                
                                self.update_signal.emit(f"[线程{self.thread_id}] 紧急内存清理完成")
                            except Exception as e:
                                self.update_signal.emit(f"[线程{self.thread_id}] 紧急内存清理失败: {str(e)}")
                    
                    # 每10秒执行一次常规内存清理
                    if i % 10 == 0:
                        try:
                            # 执行更高效的垃圾回收
                            gc.collect(2)  # Python端垃圾回收
                            driver.execute_script("window.gc();")  # 浏览器端垃圾回收
                            
                            # 定期重置浏览器缓存
                            current_time = time.time()
                            if current_time - last_memory_cleanup > 60:  # 每60秒执行一次深度清理
                                last_memory_cleanup = current_time
                                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                                driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                            # 清理不必要的资源
                            driver.execute_script("""
                            // 增强版内存清理
                            if (window.performance && window.performance.memory) {
                                console.log('清理前内存:', window.performance.memory.usedJSHeapSize / 1048576, 'MB');
                            }
                            
                            // 清除未使用的媒体资源
                            const allMedia = document.querySelectorAll('img, video, audio, canvas, svg');
                            allMedia.forEach(media => {
                                if (!isElementInViewport(media)) {
                                    if (media.tagName === 'IMG') {
                                        media.src = '';
                                        media.srcset = '';
                                    } else if (media.tagName === 'VIDEO' || media.tagName === 'AUDIO') {
                                        media.pause();
                                        media.src = '';
                                        media.load();
                                    } else if (media.tagName === 'CANVAS') {
                                        const ctx = media.getContext('2d');
                                        if (ctx) ctx.clearRect(0, 0, media.width, media.height);
                                    }
                                }
                            });
                            
                            // 移除不可见的iframe
                            const iframes = document.querySelectorAll('iframe');
                            iframes.forEach(iframe => {
                                if (!isElementInViewport(iframe)) {
                                    iframe.src = 'about:blank';
                                }
                            });
                            
                            // 清理DOM事件监听器
                            const nonEssentialElements = document.querySelectorAll('.comment-container, .recommend-container, .video-toolbar');
                            nonEssentialElements.forEach(el => {
                                const clone = el.cloneNode(true);
                                if (el.parentNode) {
                                    el.parentNode.replaceChild(clone, el);
                                }
                            });
                            
                            function isElementInViewport(el) {
                                const rect = el.getBoundingClientRect();
                                return (
                                    rect.top >= 0 &&
                                    rect.left >= 0 &&
                                    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                                    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                                );
                            }
                            """)
                            self.update_signal.emit(f"[线程{self.thread_id}] 已执行内存清理")
                        except Exception as e:
                            self.update_signal.emit(f"[线程{self.thread_id}] 内存清理时出错: {str(e)}")
                    
                    if i % 5 == 0 or i <= 5:  # 每5秒更新一次，最后5秒每秒更新
                        self.update_signal.emit(f"[线程{self.thread_id}] 剩余观看时间: {i} 秒")
                    time.sleep(1)
                
                # 任务完成
                self.update_signal.emit(f"[线程{self.thread_id}] 观看任务完成！")
                break  # 成功完成，退出重试循环
                
            except WebDriverException as e:
                retry_count += 1
                error_msg = str(e)
                self.update_signal.emit(f"[线程{self.thread_id}] 浏览器错误: {error_msg}")
                
                if "net::ERR_" in error_msg:
                    self.update_signal.emit(f"[线程{self.thread_id}] 网络连接错误，请检查网络连接")
                elif "chrome not reachable" in error_msg.lower():
                    self.update_signal.emit(f"[线程{self.thread_id}] 无法连接到Chrome浏览器")
                
                if retry_count < self.max_retries and self.is_running:
                    self.update_signal.emit(f"[线程{self.thread_id}] 将在3秒后进行第{retry_count+1}次重试...")
                    time.sleep(3)
                else:
                    self.update_signal.emit(f"[线程{self.thread_id}] 达到最大重试次数，任务失败")
                    
            except Exception as e:
                self.update_signal.emit(f"[线程{self.thread_id}] 发生错误: {str(e)}")
                self.update_signal.emit(traceback.format_exc())
                break
                
            finally:
                # 关闭浏览器并清理资源
                if driver:
                    try:
                        # 在关闭前尝试清理内存
                        try:
                            # 清除所有cookies
                            driver.delete_all_cookies()
                            
                            # 执行更高效的垃圾回收
                            gc.collect(2)  # Python端垃圾回收
                            driver.execute_script("window.gc();")  # 浏览器端垃圾回收
                            
                            # 定期重置浏览器缓存
                            current_time = time.time()
                            if current_time - last_memory_cleanup > 60:  # 每60秒执行一次深度清理
                                last_memory_cleanup = current_time
                                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                                driver.execute_cdp_cmd('Network.clearBrowserCookies', {})  
                            
                            # 清除本地存储
                            driver.execute_script("window.localStorage.clear();")  
                            driver.execute_script("window.sessionStorage.clear();")  
                            
                            # 关闭所有标签页，只保留当前页
                            original_handle = driver.current_window_handle
                            for handle in driver.window_handles:
                                if handle != original_handle:
                                    driver.switch_to.window(handle)
                                    driver.close()
                            driver.switch_to.window(original_handle)
                            
                            self.update_signal.emit(f"[线程{self.thread_id}] 浏览器资源已清理")
                        except Exception as e:
                            self.update_signal.emit(f"[线程{self.thread_id}] 清理资源时发生错误: {str(e)}")
                        
                        # 关闭浏览器
                        driver.quit()
                        self.update_signal.emit(f"[线程{self.thread_id}] 浏览器已关闭")
                    except Exception as e:
                        self.update_signal.emit(f"[线程{self.thread_id}] 关闭浏览器时发生错误: {str(e)}")
                    
                    # 强制进行Python垃圾回收
                    import gc
                    gc.collect()
                    self.update_signal.emit(f"[线程{self.thread_id}] 系统资源已回收")
        
        self.finished_signal.emit()
    
    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser_workers = []  # 存储多个工作线程
        self.max_retries = 3  # 默认最大重试次数
        self.thread_count = 1  # 默认线程数量
        
        # 语言资源字典
        self.lang_resources = {
            "zh_CN": {
                "window_title": "BioFna - B站播放量助手",
                "app_title": "BioFna - B站播放量助手",
                "video_url": "视频链接:",
                "url_placeholder": "请输入B站视频链接 (https://www.bilibili.com/video/...)",
                "watch_time": "观看时间:",
                "seconds": " 秒",
                "headless_mode": "无头模式",
                "headless_tooltip": "启用后浏览器将在后台运行，不显示界面",
                "show_window": "显示窗口",
                "show_window_tooltip": "是否显示浏览器窗口（非无头模式下有效）",
                "thread_count": "线程数量:",
                "max_retries": "最大重试次数:",
                "start_task": "开始任务",
                "stop_task": "停止任务",
                "log_area": "运行日志:",
                "status_ready": "就绪",
                "status_running": "任务运行中...",
                "input_error": "输入错误",
                "invalid_url": "请输入有效的B站视频链接！",
                "task_started": "任务开始...",
                "video_link": "视频链接: {}",
                "watch_time_log": "观看时间: {}秒",
                "headless_log": "无头模式: {}",
                "show_window_log": "显示窗口: {}",
                "thread_count_log": "线程数量: {}",
                "max_retries_log": "最大重试次数: {}",
                "thread_started": "线程 {} 已启动",
                "stopping_tasks": "正在停止所有任务...",
                "all_tasks_ended": "所有任务已结束",
                "on": "开启",
                "off": "关闭",
                "language": "语言:"
            },
            "en_US": {
                "window_title": "BioFna - Bilibili View Assistant",
                "app_title": "BioFna - Bilibili View Assistant",
                "video_url": "Video URL:",
                "url_placeholder": "Enter Bilibili video link (https://www.bilibili.com/video/...)",
                "watch_time": "Watch Time:",
                "seconds": " sec",
                "headless_mode": "Headless Mode",
                "headless_tooltip": "Browser will run in background without UI when enabled",
                "show_window": "Show Window",
                "show_window_tooltip": "Whether to show browser window (effective when not in headless mode)",
                "thread_count": "Thread Count:",
                "max_retries": "Max Retries:",
                "start_task": "Start Task",
                "stop_task": "Stop Task",
                "log_area": "Logs:",
                "status_ready": "Ready",
                "status_running": "Task running...",
                "input_error": "Input Error",
                "invalid_url": "Please enter a valid Bilibili video link!",
                "task_started": "Task started...",
                "video_link": "Video link: {}",
                "watch_time_log": "Watch time: {} seconds",
                "headless_log": "Headless mode: {}",
                "show_window_log": "Show window: {}",
                "thread_count_log": "Thread count: {}",
                "max_retries_log": "Max retries: {}",
                "thread_started": "Thread {} started",
                "stopping_tasks": "Stopping all tasks...",
                "all_tasks_ended": "All tasks ended",
                "on": "On",
                "off": "Off",
                "language": "Language:"
            }
        }
        
        # 加载设置
        self.settings = QSettings("BioFna", "BioFnaApp")
        self.current_language = self.settings.value("language", "zh_CN")
        
        # 设置应用图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BioFna ico.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # 设置全局默认字体
        self.default_font = QFont("Microsoft YaHei", 9)
        QApplication.setFont(self.default_font)
        
        self.init_ui()
        
    def init_ui(self):
        # 设置窗口
        self.setWindowTitle(self.lang_resources[self.current_language]["window_title"])
        self.setFixedSize(650, 450)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 顶部布局（标题和语言选择）
        top_layout = QHBoxLayout()
        
        # 标题
        self.title_label = QLabel(self.lang_resources[self.current_language]["app_title"])
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Microsoft YaHei", 18, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        top_layout.addWidget(self.title_label, 4)  # 分配更多空间给标题
        
        # 语言选择
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel(self.lang_resources[self.current_language]["language"])
        self.lang_label.setFont(QFont("Microsoft YaHei", 9))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("中文", "zh_CN")
        self.lang_combo.addItem("English", "en_US")
        
        # 设置当前语言
        index = 0 if self.current_language == "zh_CN" else 1
        self.lang_combo.setCurrentIndex(index)
        
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo)
        top_layout.addLayout(lang_layout, 1)  # 分配较少空间给语言选择
        
        main_layout.addLayout(top_layout)
        
        # 视频URL输入
        url_layout = QHBoxLayout()
        self.url_label = QLabel(self.lang_resources[self.current_language]["video_url"])
        self.url_label.setFixedWidth(80)
        self.url_label.setFont(QFont("Microsoft YaHei", 10))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.lang_resources[self.current_language]["url_placeholder"])
        self.url_input.setFont(QFont("Microsoft YaHei", 9))
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)
        
        # 观看时间设置
        time_layout = QHBoxLayout()
        self.time_label = QLabel(self.lang_resources[self.current_language]["watch_time"])
        self.time_label.setFixedWidth(80)
        self.time_label.setFont(QFont("Microsoft YaHei", 10))
        self.time_input = QSpinBox()
        self.time_input.setRange(5, 600)  # 5秒到10分钟
        self.time_input.setValue(30)  # 默认30秒
        self.time_input.setSuffix(self.lang_resources[self.current_language]["seconds"])
        self.time_input.setFont(QFont("Microsoft YaHei", 9))
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_input)
        time_layout.addStretch()
        main_layout.addLayout(time_layout)
        
        # 高级设置
        settings_layout = QHBoxLayout()
        
        # 无头模式选项
        self.headless_checkbox = QCheckBox(self.lang_resources[self.current_language]["headless_mode"])
        self.headless_checkbox.setToolTip(self.lang_resources[self.current_language]["headless_tooltip"])
        self.headless_checkbox.setFont(QFont("Microsoft YaHei", 9))
        settings_layout.addWidget(self.headless_checkbox)
        
        # 显示窗口选项
        self.show_window_checkbox = QCheckBox(self.lang_resources[self.current_language]["show_window"])
        self.show_window_checkbox.setChecked(True)
        self.show_window_checkbox.setToolTip(self.lang_resources[self.current_language]["show_window_tooltip"])
        self.show_window_checkbox.setFont(QFont("Microsoft YaHei", 9))
        settings_layout.addWidget(self.show_window_checkbox)
        
        # 线程数量设置
        self.thread_label = QLabel(self.lang_resources[self.current_language]["thread_count"])
        self.thread_label.setFont(QFont("Microsoft YaHei", 9))
        self.thread_input = QSpinBox()
        self.thread_input.setRange(1, 10)
        self.thread_input.setValue(self.thread_count)
        self.thread_input.valueChanged.connect(self.update_thread_count)
        self.thread_input.setFont(QFont("Microsoft YaHei", 9))
        settings_layout.addWidget(self.thread_label)
        settings_layout.addWidget(self.thread_input)
        
        # 重试次数设置
        self.retry_label = QLabel(self.lang_resources[self.current_language]["max_retries"])
        self.retry_label.setFont(QFont("Microsoft YaHei", 9))
        self.retry_input = QSpinBox()
        self.retry_input.setRange(1, 5)
        self.retry_input.setValue(self.max_retries)
        self.retry_input.valueChanged.connect(self.update_max_retries)
        self.retry_input.setFont(QFont("Microsoft YaHei", 9))
        settings_layout.addWidget(self.retry_label)
        settings_layout.addWidget(self.retry_input)
        
        settings_layout.addStretch()
        main_layout.addLayout(settings_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton(self.lang_resources[self.current_language]["start_task"])
        self.start_button.setFixedHeight(40)
        self.start_button.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.start_button.clicked.connect(self.start_task)
        
        self.stop_button = QPushButton(self.lang_resources[self.current_language]["stop_task"])
        self.stop_button.setFixedHeight(40)
        self.stop_button.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_task)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        
        # 日志区域
        self.log_label = QLabel(self.lang_resources[self.current_language]["log_area"])
        self.log_label.setFont(QFont("Microsoft YaHei", 10))
        main_layout.addWidget(self.log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFixedHeight(150)
        self.log_display.setFont(QFont("Microsoft YaHei", 9))
        main_layout.addWidget(self.log_display)
        
        # 状态栏
        self.statusBar().setFont(QFont("Microsoft YaHei", 9))
        self.statusBar().showMessage(self.lang_resources[self.current_language]["status_ready"])
    
    def update_max_retries(self, value):
        self.max_retries = value
        
    def update_thread_count(self, value):
        self.thread_count = value
        
    def change_language(self, index):
        # 获取选择的语言代码
        self.current_language = self.lang_combo.itemData(index)
        
        # 保存语言设置
        self.settings.setValue("language", self.current_language)
        
        # 更新UI文本
        self.setWindowTitle(self.lang_resources[self.current_language]["window_title"])
        self.title_label.setText(self.lang_resources[self.current_language]["app_title"])
        self.lang_label.setText(self.lang_resources[self.current_language]["language"])
        self.url_label.setText(self.lang_resources[self.current_language]["video_url"])
        self.url_input.setPlaceholderText(self.lang_resources[self.current_language]["url_placeholder"])
        self.time_label.setText(self.lang_resources[self.current_language]["watch_time"])
        self.time_input.setSuffix(self.lang_resources[self.current_language]["seconds"])
        self.headless_checkbox.setText(self.lang_resources[self.current_language]["headless_mode"])
        self.headless_checkbox.setToolTip(self.lang_resources[self.current_language]["headless_tooltip"])
        self.show_window_checkbox.setText(self.lang_resources[self.current_language]["show_window"])
        self.show_window_checkbox.setToolTip(self.lang_resources[self.current_language]["show_window_tooltip"])
        self.thread_label.setText(self.lang_resources[self.current_language]["thread_count"])
        self.retry_label.setText(self.lang_resources[self.current_language]["max_retries"])
        self.start_button.setText(self.lang_resources[self.current_language]["start_task"])
        self.stop_button.setText(self.lang_resources[self.current_language]["stop_task"])
        self.log_label.setText(self.lang_resources[self.current_language]["log_area"])
        self.statusBar().showMessage(self.lang_resources[self.current_language]["status_ready"])
        
    def start_task(self):
        # 获取视频URL
        video_url = self.url_input.text().strip()
        if not video_url or not video_url.startswith("https://www.bilibili.com/video/"):
            QMessageBox.warning(self, self.lang_resources[self.current_language]["input_error"], 
                               self.lang_resources[self.current_language]["invalid_url"])
            return
        
        # 获取观看时间
        watch_time = self.time_input.value()
        
        # 获取设置
        headless_mode = self.headless_checkbox.isChecked()
        show_window = self.show_window_checkbox.isChecked()
        thread_count = self.thread_input.value()
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.url_input.setEnabled(False)
        self.time_input.setEnabled(False)
        self.headless_checkbox.setEnabled(False)
        self.show_window_checkbox.setEnabled(False)
        self.thread_input.setEnabled(False)
        self.retry_input.setEnabled(False)
        self.statusBar().showMessage(self.lang_resources[self.current_language]["status_running"])
        
        # 清空日志
        self.log_display.clear()
        self.add_log(self.lang_resources[self.current_language]["task_started"])
        self.add_log(self.lang_resources[self.current_language]["video_link"].format(video_url))
        self.add_log(self.lang_resources[self.current_language]["watch_time_log"].format(watch_time))
        
        # 获取开启/关闭的本地化文本
        on_text = self.lang_resources[self.current_language]["on"]
        off_text = self.lang_resources[self.current_language]["off"]
        
        self.add_log(self.lang_resources[self.current_language]["headless_log"].format(on_text if headless_mode else off_text))
        self.add_log(self.lang_resources[self.current_language]["show_window_log"].format(on_text if show_window else off_text))
        self.add_log(self.lang_resources[self.current_language]["thread_count_log"].format(thread_count))
        self.add_log(self.lang_resources[self.current_language]["max_retries_log"].format(self.max_retries))
        
        # 清空之前的工作线程列表
        self.browser_workers = []
        
        # 创建并启动多个工作线程
        for i in range(1, thread_count + 1):
            worker = BrowserWorker(video_url, watch_time, headless_mode, show_window, self.max_retries, i)
            worker.update_signal.connect(self.add_log)
            worker.finished_signal.connect(self.check_all_finished)
            self.browser_workers.append(worker)
            worker.start()
            self.add_log(self.lang_resources[self.current_language]["thread_started"].format(i))
    
    def stop_task(self):
        if self.browser_workers:
            self.add_log(self.lang_resources[self.current_language]["stopping_tasks"])
            for worker in self.browser_workers:
                if worker.isRunning():
                    worker.stop()
    
    def check_all_finished(self):
        # 检查是否所有线程都已完成
        all_finished = True
        for worker in self.browser_workers:
            if worker.isRunning():
                all_finished = False
                break
        
        if all_finished:
            self.task_finished()
    
    def task_finished(self):
        # 恢复UI状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.url_input.setEnabled(True)
        self.time_input.setEnabled(True)
        self.headless_checkbox.setEnabled(True)
        self.show_window_checkbox.setEnabled(True)
        self.thread_input.setEnabled(True)
        self.retry_input.setEnabled(True)
        self.statusBar().showMessage(self.lang_resources[self.current_language]["status_ready"])
        self.add_log(self.lang_resources[self.current_language]["all_tasks_ended"])
    
    def add_log(self, message):
        self.log_display.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        # 自动滚动到底部
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())