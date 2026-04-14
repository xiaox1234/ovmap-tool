import os
import sys
import time
import json
import re
import urllib.parse
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ================= 兼容 EXE 路径 =================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================= 启动浏览器 =================
def start_browser():
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")

        driver_path = resource_path("chromedriver.exe")
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print("启动失败：", e)

# ================= 主界面 =================
import tkinter as tk
root = tk.Tk()
root.title("奥维图源工具 EXE 版")
root.geometry("500x400")
tk.Label(root, text="EXE 打包测试成功", font=("微软雅黑",14)).pack(pady=30)
root.mainloop()
