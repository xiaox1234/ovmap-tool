#!/usr/bin/env python3
"""
奥维地图图源生成工具【终极稳定版·修复tkinter错误】
已优化：{$s}子域、完整二维码、日志、网络检测、修复tkinter布局错误
"""

import os
import sys
import re
import json
import urllib.parse
import traceback
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET
import qrcode
import requests

# ================== 日志系统（替代静默输出，方便排错） ==================
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ovtool_log.txt")
def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}] {msg}\n")
    except:
        pass

# 捕获崩溃日志
def excepthook(exc_type, exc_value, exc_traceback):
    log("CRASH: " + repr(exc_value))
    log("TRACE: " + "".join(traceback.format_tb(exc_traceback)))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = excepthook
log("工具启动")

# ================== EXE 路径兼容 ==================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================== 数据结构（完整参数） ==================
@dataclass
class TileSourceConfig:
    map_id: int = 300
    map_name: str = "Google卫星图"
    host_name: str = "mt{$s}.google.com"
    url_template: str = "/vt/lyrs=s&gl=CN&x={$x}&y={$y}&z={$z}&s={$s}"
    port: int = 443
    protocol: str = "https"
    min_level: int = 1
    max_level: int = 23
    proj_type: str = "墨卡托中国"
    img_type: str = "影像地图"
    img_format: str = "jpg"
    img_size: int = 256

# ================== 核心生成器 ==================
class OvitalMapGenerator:
    # 支持 {$s} 多子域轮询 mt0/mt1/mt2/mt3
    GOOGLE_TEMPLATES = {
        "卫星图": {
            "name": "Google卫星图",
            "host": "mt{$s}.google.com",
            "url": "/vt/lyrs=s&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}&s={$s}",
            "protocol": "https",
            "port": 443,
            "img_type": "影像地图"
        },
        "混合图": {
            "name": "Google混合图",
            "host": "mt{$s}.google.com",
            "url": "/vt/lyrs=s,h&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}&s={$s}",
            "protocol": "https",
            "port": 443,
            "img_type": "影像地图"
        },
        "道路图": {
            "name": "Google道路图",
            "host": "mt{$s}.google.com",
            "url": "/vt/lyrs=m&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}&s={$s}",
            "protocol": "https",
            "port": 443,
            "img_type": "普通地图"
        },
        "地形图": {
            "name": "Google地形图",
            "host": "mt{$s}.google.com",
            "url": "/vt/lyrs=p&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}&s={$s}",
            "protocol": "https",
            "port": 443,
            "img_type": "普通地图"
        }
    }

    def create_google_source(self, template_key="卫星图") -> TileSourceConfig:
        t = self.GOOGLE_TEMPLATES[template_key]
        return TileSourceConfig(
            map_name=t["name"],
            host_name=t["host"],
            url_template=t["url"],
            protocol=t["protocol"],
            port=t["port"],
            img_type=t["img_type"]
        )

    # ================== 网络连通性检测 ==================
    def check_network(self):
        try:
            test_url = "https://mt0.google.com/vt/lyrs=s&x=0&y=0&z=0"
            requests.head(test_url, timeout=3)
            return True
        except:
            return False

    # ================== 奥维官方完整二维码 ==================
    def generate_qrcode(self, config: TileSourceConfig, save_path):
        params = {
            "name": config.map_name,
            "host": config.host_name,
            "url": config.url_template,
            "proj": config.proj_type,
            "protocol": config.protocol,
            "port": str(config.port),
            "minzoom": str(config.min_level),
            "maxzoom": str(config.max_level),
            "type": config.img_type
        }
        qr_data = f"omap://custommap?{urllib.parse.urlencode(params)}"
        log(f"二维码内容: {qr_data}")
        
        qr = qrcode.QRCode(version=4, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(save_path)

    # ================== 导出 ovmap 配置文件 ==================
    def export_ovmap(self, config: TileSourceConfig, path):
        root = ET.Element("OvaMap")
        ET.SubElement(root, "MapID").text = str(config.map_id)
        ET.SubElement(root, "MapName").text = config.map_name
        ET.SubElement(root, "HostName").text = config.host_name
        ET.SubElement(root, "URL").text = config.url_template
        ET.SubElement(root, "Port").text = str(config.port)
        ET.SubElement(root, "Protocol").text = config.protocol
        ET.SubElement(root, "MinLevel").text = str(config.min_level)
        ET.SubElement(root, "MaxLevel").text = str(config.max_level)
        ET.SubElement(root, "Projection").text = config.proj_type
        ET.SubElement(root, "ImageType").text = config.img_type
        ET.SubElement(root, "ImageFormat").text = config.img_format
        ET.SubElement(root, "ImageSize").text = str(config.img_size)
        ET.SubElement(root, "ServerID").text = "mt{$s}"
        
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        log(f"导出配置: {path}")

    def export_all(self, config: TileSourceConfig, base_path):
        self.export_ovmap(config, f"{base_path}.ovmap")
        self.generate_qrcode(config, f"{base_path}.png")

# ================== GUI 界面（修复tkinter布局错误） ==================
def create_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except Exception as e:
        log(f"导入GUI库失败: {str(e)}")
        return

    root = tk.Tk()
    root.title("奥维地图图源生成器【终极版】")
    root.geometry("720x600")
    root.resizable(False, False)
    gen = OvitalMapGenerator()

    # ---------- 逻辑 ----------
    def select_path():
        p = filedialog.askdirectory()
        if p:
            path_var.set(p)

    def build():
        tp = template_var.get()
        fname = name_var.get()
        save_dir = path_var.get()
        if not save_dir:
            save_dir = os.path.expanduser("~/Desktop")
        full_path = os.path.join(save_dir, fname)

        # 网络检测
        ok = gen.check_network()
        if not ok:
            res = messagebox.askyesno("网络提示", "检测到当前网络可能无法直接访问Google地图\n可能出现 No Data(-5)\n是否继续生成？")
            if not res:
                return

        try:
            cfg = gen.create_google_source(tp)
            gen.export_all(cfg, full_path)
            messagebox.showinfo("成功", f"生成完成！\n{full_path}.ovmap\n{full_path}.png")
            log("生成成功")
        except Exception as e:
            log(f"生成失败: {str(e)}")
            messagebox.showerror("错误", str(e))

    # ---------- 布局（修复所有-pad错误，改用padx/pady） ----------
    tk.Label(root, text="奥维互动地图 图源生成工具", font=("微软雅黑", 16, "bold")).pack(pady=15)

    frame = ttk.LabelFrame(root, text="参数配置", padding=15)
    frame.pack(fill="x", padx=20, pady=10)

    # 模板选择
    ttk.Label(frame, text="预设模板：").grid(row=0, column=0, sticky="w", pady=6, padx=5)
    template_var = tk.StringVar(value="卫星图")
    ttk.Combobox(frame, textvariable=template_var, 
                 values=["卫星图","混合图","道路图","地形图"], 
                 width=18, state="readonly").grid(row=0, column=1, sticky="w", pady=6, padx=5)

    # 文件名称
    ttk.Label(frame, text="文件名称：").grid(row=1, column=0, sticky="w", pady=6, padx=5)
    name_var = tk.StringVar(value="Google卫星图")
    ttk.Entry(frame, textvariable=name_var, width=25).grid(row=1, column=1, sticky="w", pady=6, padx=5)

    # 保存位置
    ttk.Label(frame, text="保存位置：").grid(row=2, column=0, sticky="w", pady=6, padx=5)
    path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop"))
    ttk.Entry(frame, textvariable=path_var, width=35).grid(row=2, column=1, sticky="w", pady=6, padx=5)
    ttk.Button(frame, text="浏览", command=select_path, width=8).grid(row=2, column=2, padx=5, pady=6)

    # 生成按钮
    ttk.Button(root, text="▶ 生成图源文件 + 可扫描二维码", command=build, width=38).pack(pady=18)

    # 使用说明
    msg = """使用说明：
① 生成后直接导入 .ovmap 文件到奥维
② 或扫描二维码一键添加
③ 出现 No Data(-5) 是网络环境问题，非配置错误
④ 支持 mt0-mt3 自动轮询，加载更快"""
    tk.Label(root, text=msg, fg="#444", justify="left").pack(pady=5, padx=20)

    root.mainloop()

# ================== 启动 ==================
if __name__ == "__main__":
    create_gui()
