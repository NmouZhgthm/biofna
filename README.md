# BioFna - B站播放量助手

## 简介

BioFna是一个功能强大的B站视频播放量助手工具，专为内容创作者设计。它能自动打开B站视频链接并在指定时间内观看，帮助提升视频的播放量和观看时长。本工具采用多线程技术，大幅提高效率，同时通过内存优化确保长时间运行的稳定性。

## 功能特点

- **简洁直观的图形用户界面**：易于操作，适合各类用户
- **多线程并发观看**：最多可开启10个线程，显著提高效率
- **自定义观看时间**：灵活设置5秒至10分钟的观看时长
- **无头模式**：浏览器在后台运行，不显示界面，减少资源占用
- **智能重试机制**：遇到网络问题自动重试，最多可设置5次重试
- **实时运行日志**：详细记录每个操作步骤和状态
- **内置ChromeDriver**：使用本地驱动，无需每次下载
- **内存优化技术**：

   - 自动监控和清理浏览器资源
   - 定期执行垃圾回收
   - 智能限制内存使用上限
   - 移除不必要的页面元素

- **多语言支持**：完整支持中文和英文界面，可随时切换
- **配置保存**：自动记住上次的设置，提高使用便捷性

## 使用方法

1. 启动应用程序
2. 在"视频链接"输入框中粘贴B站视频URL（格式：https://www.bilibili.com/video/...）
3. 设置观看时间（默认30秒）
4. 调整线程数量（1-10个线程）
5. 可选：勾选"无头模式"在后台运行浏览器
6. 可选：调整最大重试次数（默认3次）
7. 可选：选择界面语言（中文/英文）
8. 点击"开始任务"按钮开始执行
9. 任务执行过程中可以通过"停止任务"按钮随时中断
10. 查看运行日志了解任务执行情况

## 系统要求

- Windows操作系统
- Google Chrome浏览器
- 网络连接

## 安装方法

### 方法一：直接使用打包版本

下载已打包的可执行文件（BioFna.exe），双击即可运行，无需安装Python环境。

### 方法二：从源码运行

1. 确保已安装Python 3.6+
2. 克隆或下载本仓库
3. 安装依赖项：

```sh
pip install -r requirements.txt
```

4. 运行主程序：

```sh
python main.py
```

## 依赖项

本项目依赖以下Python库：

- PyQt6 6.6.1 - 图形用户界面
- selenium 4.15.2 - 浏览器自动化
- webdriver-manager 4.0.1 - WebDriver管理
- psutil 5.9.5 - 进程和系统监控

## 注意事项

- 本工具仅供学习和研究使用
- 请勿过度使用，以免违反B站用户协议
- 如遇到网络连接问题，请检查网络设置或增加重试次数
- 长时间运行可能会占用较多系统资源，建议定期关闭程序释放资源
- 如果本地没有ChromeDriver，程序会尝试自动下载

## 打包说明

本项目可以使用Nuitka打包为独立的Windows可执行文件，无需安装Python环境即可运行。Nuitka是一个Python编译器，可以将Python代码转换为可执行文件，提供更好的性能和保护源代码。

### 使用Nuitka打包步骤

1. 安装Nuitka：

```sh
pip install nuitka
```

2. 使用以下命令进行打包：

```ini
python -m nuitka --standalone --onefile --windows-icon-from-ico=BioFna.ico --enable-plugin=pyqt6 --include-package=selenium --include-package=webdriver_manager --include-package=psutil --include-data-dir=chromedriver-win64=chromedriver-win64 --windows-console-mode=disable --output-filename=BioFna.exe main.py
```

3. 打包完成后，将在当前目录生成`BioFna.exe`文件，双击即可运行

### 打包参数说明

- `--standalone`：创建独立的可执行文件，包含所有依赖
- `--onefile`：将所有文件打包为单个可执行文件
- `--windows-icon-from-ico`：设置应用程序图标
- `--enable-plugin=pyqt6`：启用PyQt6插件支持
- `--include-package=selenium`：包含selenium包
- `--include-package=webdriver_manager`：包含webdriver_manager包
- `--include-package=psutil`：包含psutil包
- `--include-data-dir=chromedriver-win64=chromedriver-win64`：包含ChromeDriver目录
- `--windows-disable-console`：禁用控制台窗口
- `--output-filename=BioFna.exe`：指定输出文件名为BioFna.exe

### 打包优化建议

- 如果打包后的文件过大，可以考虑使用`--nofollow-import-to=*.tests`排除测试文件
- 对于不需要的模块，可以使用`--nofollow-import-to=模块名`排除
- 如需减小文件体积，可以添加`--remove-output`参数在打包完成后删除中间文件
- 如果遇到打包错误，可以尝试添加`--disable-console`和`--assume-yes-for-downloads`参数

## 技术实现

- 使用PyQt6构建跨平台图形界面
- 基于Selenium WebDriver实现浏览器自动化
- 采用多线程技术提高并发效率
- 实现先进的内存监控和优化机制：
  - 更频繁的内存使用检查（5秒间隔）
  - 降低单线程内存上限（400MB）
  - 多级垃圾回收策略（Python和浏览器双重GC）
  - 智能清理大型对象和缓存
  - 定期深度清理浏览器资源
- 浏览器资源优化：
  - 禁用动画和过渡效果
  - 批量DOM操作减少重排重绘
  - 智能管理媒体资源和质量
  - 优化事件监听器
- 使用QSettings保存用户配置
- 支持多语言国际化