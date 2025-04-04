import sys
import os
import time
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QSpinBox, QTextEdit, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
        
    def run(self):
        driver = None
        retry_count = 0
        
        while retry_count < self.max_retries and self.is_running:
            try:
                self.update_signal.emit(f"[线程{self.thread_id}] 正在启动浏览器...")
                
                # 配置Chrome选项
                chrome_options = Options()
                chrome_options.add_argument("--incognito")  # 无痕模式
                chrome_options.add_argument("--mute-audio")  # 静音
                chrome_options.add_argument("--disable-extensions")  # 禁用扩展
                chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
                chrome_options.add_argument("--no-sandbox")  # 禁用沙盒模式
                chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用
                
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
                
                # 打开视频
                self.update_signal.emit(f"[线程{self.thread_id}] 正在打开视频: {self.video_url}")
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
                
                # 倒计时
                for i in range(self.watch_time, 0, -1):
                    if not self.is_running:
                        break
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
                # 关闭浏览器
                if driver:
                    try:
                        driver.quit()
                        self.update_signal.emit(f"[线程{self.thread_id}] 浏览器已关闭")
                    except Exception:
                        self.update_signal.emit(f"[线程{self.thread_id}] 关闭浏览器时发生错误")
        
        self.finished_signal.emit()
    
    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser_workers = []  # 存储多个工作线程
        self.max_retries = 3  # 默认最大重试次数
        self.thread_count = 1  # 默认线程数量
        self.init_ui()
        
    def init_ui(self):
        # 设置窗口
        self.setWindowTitle("BioFna - B站播放量助手")
        self.setFixedSize(650, 450)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("BioFna - B站播放量助手")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        main_layout.addWidget(title_label)
        
        # 视频URL输入
        url_layout = QHBoxLayout()
        url_label = QLabel("视频链接:")
        url_label.setFixedWidth(80)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入B站视频链接 (https://www.bilibili.com/video/...)")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)
        
        # 观看时间设置
        time_layout = QHBoxLayout()
        time_label = QLabel("观看时间:")
        time_label.setFixedWidth(80)
        self.time_input = QSpinBox()
        self.time_input.setRange(5, 600)  # 5秒到10分钟
        self.time_input.setValue(30)  # 默认30秒
        self.time_input.setSuffix(" 秒")
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_input)
        time_layout.addStretch()
        main_layout.addLayout(time_layout)
        
        # 高级设置
        settings_layout = QHBoxLayout()
        
        # 无头模式选项
        self.headless_checkbox = QCheckBox("无头模式")
        self.headless_checkbox.setToolTip("启用后浏览器将在后台运行，不显示界面")
        settings_layout.addWidget(self.headless_checkbox)
        
        # 显示窗口选项
        self.show_window_checkbox = QCheckBox("显示窗口")
        self.show_window_checkbox.setChecked(True)
        self.show_window_checkbox.setToolTip("是否显示浏览器窗口（非无头模式下有效）")
        settings_layout.addWidget(self.show_window_checkbox)
        
        # 线程数量设置
        thread_label = QLabel("线程数量:")
        self.thread_input = QSpinBox()
        self.thread_input.setRange(1, 10)
        self.thread_input.setValue(self.thread_count)
        self.thread_input.valueChanged.connect(self.update_thread_count)
        settings_layout.addWidget(thread_label)
        settings_layout.addWidget(self.thread_input)
        
        # 重试次数设置
        retry_label = QLabel("最大重试次数:")
        self.retry_input = QSpinBox()
        self.retry_input.setRange(1, 5)
        self.retry_input.setValue(self.max_retries)
        self.retry_input.valueChanged.connect(self.update_max_retries)
        settings_layout.addWidget(retry_label)
        settings_layout.addWidget(self.retry_input)
        
        settings_layout.addStretch()
        main_layout.addLayout(settings_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始任务")
        self.start_button.setFixedHeight(40)
        self.start_button.clicked.connect(self.start_task)
        
        self.stop_button = QPushButton("停止任务")
        self.stop_button.setFixedHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_task)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        
        # 日志区域
        log_label = QLabel("运行日志:")
        main_layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFixedHeight(150)
        main_layout.addWidget(self.log_display)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def update_max_retries(self, value):
        self.max_retries = value
        
    def update_thread_count(self, value):
        self.thread_count = value
        
    def start_task(self):
        # 获取视频URL
        video_url = self.url_input.text().strip()
        if not video_url or not video_url.startswith("https://www.bilibili.com/video/"):
            QMessageBox.warning(self, "输入错误", "请输入有效的B站视频链接！")
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
        self.statusBar().showMessage("任务运行中...")
        
        # 清空日志
        self.log_display.clear()
        self.add_log("任务开始...")
        self.add_log(f"视频链接: {video_url}")
        self.add_log(f"观看时间: {watch_time}秒")
        self.add_log(f"无头模式: {'开启' if headless_mode else '关闭'}")
        self.add_log(f"显示窗口: {'开启' if show_window else '关闭'}")
        self.add_log(f"线程数量: {thread_count}")
        self.add_log(f"最大重试次数: {self.max_retries}")
        
        # 清空之前的工作线程列表
        self.browser_workers = []
        
        # 创建并启动多个工作线程
        for i in range(1, thread_count + 1):
            worker = BrowserWorker(video_url, watch_time, headless_mode, show_window, self.max_retries, i)
            worker.update_signal.connect(self.add_log)
            worker.finished_signal.connect(self.check_all_finished)
            self.browser_workers.append(worker)
            worker.start()
            self.add_log(f"线程 {i} 已启动")
    
    def stop_task(self):
        if self.browser_workers:
            self.add_log("正在停止所有任务...")
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
        self.statusBar().showMessage("就绪")
        self.add_log("所有任务已结束")
    
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