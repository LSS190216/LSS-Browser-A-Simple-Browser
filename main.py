# PyQt6 PyQt6-WebEngine dnspython
import sys
import os
import socket
import dns.resolver
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineDownloadRequest
import requests

VERSION_URL = "https://raw.githubusercontent.com/LSS190216/LSS-Browser-A-Simple-Browser/refs/heads/main/version.txt"
UPDATE_URL = "https://raw.githubusercontent.com/LSS190216/LSS-Browser-A-Simple-Browser/refs/heads/main/main.py"
LOCAL_VERSION = "100103" #100000表示1.0.0, 100302表示1.3.2, 101213表示1.12.13

def check_update():
    try:
        print("正在检查更新...")
        r = requests.get(VERSION_URL, timeout=10)
        remote_version = r.text.strip()
        print(f"云端版本：{remote_version}，本地版本：{LOCAL_VERSION}")
        if int(remote_version) > int(LOCAL_VERSION):
            print("发现新版本！")
            return True
        return False
    except Exception as e:
        print(f"检查更新失败:{e}")
        return False

def update_file():
    try:
        print("正在下载更新")
        new_code = requests.get(UPDATE_URL, timeout=20).text
        with open(__file__, "w", encoding="utf-8", newline="") as f:
            f.write(new_code)
        print("更新成功！下次启动生效")
    except Exception as e:
        print(f"更新失败：{e}")

class UpdateThread(QThread):
    def run(self):
        if check_update():
            update_file()

# ------------------- 修复跳转的最小代码 -------------------
class FixJumpPage(QWebEnginePage):
    def __init__(self, parent):
        super().__init__(parent)
        self.main = parent.parent()
    def createWindow(self, t):
        tab = self.main.add_new_tab()
        return tab.page()
# --------------------------------------------------------

# 国内优先 DNS 列表
CUSTOM_DNS = [
    "223.5.5.5", "223.6.6.6",
    "114.114.114.114",
    "119.29.29.29", "119.28.28.28",
    "180.76.76.76",
    "180.184.1.1", "180.184.2.2",
    "1.1.1.1", "1.0.0.1",
    "8.8.8.8", "8.8.4.4",
    "9.9.9.9"
]

# 系统下载文件夹
def get_download_path():
    return os.path.join(os.path.expanduser("~"), "Downloads")

# 全局DNS解析器
dns_resolver = dns.resolver.Resolver()
dns_resolver.nameservers = CUSTOM_DNS
dns_resolver.lifetime = 2

# 网络连通性检测（TCP端口检测）
def check_connectivity(ip, port=443, timeout=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            return (True, "网络正常")
        else:
            return (False, f"网络不可达(端口{port}关闭)")
    except socket.timeout:
        return (False, "网络超时")
    except Exception as e:
        return (False, f"网络检测失败:{str(e)[:15]}")

# 通用DNS+网络双重校验方法
def resolve_and_check_domain(host):
    if not host:
        return (False, "DNS 正在解析")
    try:
        ans = dns_resolver.resolve(host, "A")
        ip = ans[0].address
        used_dns = ans.nameserver
        dns_text = f"DNS OK:{used_dns} | {host} → {ip}"
    except dns.resolver.NXDOMAIN:
        return (False, "DNS ERROR:" + host + " 域名不存在")
    except dns.resolver.Timeout:
        return (False, "DNS ERROR:" + host + " 解析超时")
    except Exception as e:
        return (False, f"DNS ERROR:{host} | {str(e)[:20]}")
    conn_success, conn_text = check_connectivity(ip)
    if conn_success:
        return (True, f"{dns_text} | {conn_text}")
    else:
        return (False, f"{dns_text} | {conn_text}")

class BrowserTab(QWebEngineView):
    def __init__(self, parent_win):
        super().__init__(parent_win)
        self.parent_win = parent_win
        self.setPage(FixJumpPage(self))
        self.page().profile().downloadRequested.connect(self.on_download)
        self.loadFinished.connect(self.on_load_finish)
        self.urlChanged.connect(self.on_url_changed)

    def on_download(self, download: QWebEngineDownloadRequest):
        download.setDownloadDirectory(get_download_path())
        download.receivedBytesChanged.connect(lambda: self.parent_win.download_progress(download.receivedBytes(), download.totalBytes()))
        download.accept()

    def on_url_changed(self, qurl):
        host = qurl.host()
        status, text = resolve_and_check_domain(host)
        self.parent_win.set_dns_text(text, status)

    def on_load_finish(self, ok):
        url = self.url().toString()
        host = QUrl(url).host()
        status, text = resolve_and_check_domain(host)
        self.parent_win.set_dns_text(text, status)
        if ok:
            self.page().runJavaScript("""document.addEventListener('click', () => {if (window.AudioContext) {let ctx = new AudioContext();ctx.resume();}});""")

class AcceleratedBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LSS浏览器")
        self.setGeometry(0, 0, 1200, 600)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)
        self.setCentralWidget(self.tab_widget)
        self.create_nav_bar()
        self.create_status_bar()
        self.add_new_tab(QUrl("https://www.baidu.com"), "主页")

    def add_new_tab(self, url=None, title="新标签页"):
        browser = BrowserTab(self)
        if url:
            browser.setUrl(url)
        else:
            browser.setUrl(QUrl("https://www.baidu.com"))
        idx = self.tab_widget.addTab(browser, title)
        self.tab_widget.setCurrentIndex(idx)
        browser.titleChanged.connect(lambda t: self.tab_widget.setTabText(idx, t))
        browser.urlChanged.connect(self.url_changed)
        return browser

    def close_tab(self, idx):
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(idx)

    def tab_changed(self, idx):
        w = self.tab_widget.currentWidget()
        if w:
            self.url_bar.setText(w.url().toString())
            host = w.url().host()
            status, text = resolve_and_check_domain(host)
            self.set_dns_text(text, status)

    def create_nav_bar(self):
        nav = QToolBar()
        self.addToolBar(nav)
        back = QAction("←", self)
        back.triggered.connect(lambda: self.tab_widget.currentWidget().back())
        nav.addAction(back)
        forward = QAction("→", self)
        forward.triggered.connect(lambda: self.tab_widget.currentWidget().forward())
        nav.addAction(forward)
        refresh = QAction("重试", self)
        refresh.triggered.connect(lambda: self.tab_widget.currentWidget().reload())
        nav.addAction(refresh)
        home = QAction("主页", self)
        home.triggered.connect(lambda: self.go_home())
        nav.addAction(home)
        new_tab = QAction("＋", self)
        new_tab.triggered.connect(self.add_new_tab)
        nav.addAction(new_tab)
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.go_url)
        nav.addWidget(self.url_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        nav.addWidget(self.progress_bar)

    def go_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith(("http://","https://")):
            url = "https://" + url
        self.tab_widget.currentWidget().setUrl(QUrl(url))

    def go_home(self):
        self.url_bar.setText("https://www.baidu.com")
        self.tab_widget.currentWidget().setUrl(QUrl("https://www.baidu.com"))

    def url_changed(self, q):
        self.url_bar.setText(q.toString())

    def create_status_bar(self):
        self.dns_label = QLabel("DNS 正在解析")
        self.down_label = QLabel("")
        self.statusBar().addWidget(self.dns_label)
        self.statusBar().addPermanentWidget(self.down_label)

    def set_dns_text(self, text, status=False):
        self.dns_label.setText(text)
        if status:
            self.dns_label.setStyleSheet("color:#008800;font-weight:bold")
        else:
            self.dns_label.setStyleSheet("color:#cc0000;font-weight:bold")

    def download_progress(self, recv, total):
        if total > 0:
            per = int(recv / total * 100)
            if per >= 100:
                self.down_label.setText("<font color='green'>下载完成</font>")
                QTimer.singleShot(5000, lambda: self.down_label.setText(""))
            else:
                self.down_label.setText(f"下载中：{per}%")
        elif recv > 0 and total == 0:
            self.down_label.setText(f"下载中：已接收 {recv/1024/1024:.2f}MB")

if __name__ == "__main__":
    print(f"当前版本：{LOCAL_VERSION[0]}.{int(LOCAL_VERSION[2]+LOCAL_VERSION[3])}.{int(LOCAL_VERSION[4]+LOCAL_VERSION[5])}")
    if sys.platform == "win32":
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--autoplay-policy=no-user-gesture-required"
    app = QApplication(sys.argv)
    win = AcceleratedBrowser()
    win.show()
    update_thread = UpdateThread()
    update_thread.start()
    sys.exit(app.exec())
