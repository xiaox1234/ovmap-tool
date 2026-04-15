#!/usr/bin/env python3
"""
奥维地图图源生成工具【最终完美版】
解决：No Data(-5) + 二维码无法识别 + 保存路径
"""

import os
import sys
import re
import json
import urllib.parse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET
import qrcode

# ================== EXE 打包兼容 ==================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# ================== 数据结构 ==================
@dataclass
class TileSourceConfig:
    map_id: int = 300
    map_name: str = "Google卫星图"
    host_name: str = "mt0.google.com"
    url_template: str = "/vt/lyrs=s&x={$x}&y={$y}&z={$z}"
    port: int = 443
    protocol: str = "https"
    max_level: int = 23
    min_level: int = 1
    proj_type: str = "墨卡托中国"
    img_type: str = "影像地图"
    img_format: str = "jpg"
    img_size: int = 256
    overlay: str = "无"
    basemap: str = "无"
    referer: str = ""
    cookies: str = ""

# ================== 奥维标准模板 ==================
class OvitalMapGenerator:
    GOOGLE_TEMPLATES = {
        "卫星图": {
            "name": "Google卫星图",
            "host": "mt0.google.com",
            "url": "/vt/lyrs=s&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "protocol": "https",
            "port": 443,
            "img_type": "影像地图"
        },
        "混合图": {
            "name": "Google混合图",
            "host": "mt0.google.com",
            "url": "/vt/lyrs=s,h&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "protocol": "https",
            "port": 443,
            "img_type": "影像地图"
        },
        "道路图": {
            "name": "Google道路图",
            "host": "mt0.google.com",
            "url": "/vt/lyrs=m&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "protocol": "https",
            "port": 443,
            "img_type": "普通地图"
        },
        "地形图": {
            "name": "Google地形图",
            "host": "mt0.google.com",
            "url": "/vt/lyrs=p&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
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

    # ================== 核心修复：奥维官方二维码格式 ==================
    def generate_qrcode(self, config: TileSourceConfig, save_path):
        params = {
            "name": config.map_name,
            "host": config.host_name,
            "url": config.url_template,
            "proj": config.proj_type,
            "protocol": config.protocol,
            "port": str(config.port)
        }
        qr_data = f"omap://custommap?{urllib.parse.urlencode(params)}"
        
        qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(save_path)

    # ================== 导出奥维配置文件 ==================
    def export_ovmap(self, config: TileSourceConfig, path):
        root = ET.Element("OvaMap")
        ET.SubElement(root, "MapID").text = str(config.map_id)
        ET.SubElement(root, "MapName").text = config.map_name
        ET.SubElement(root, "HostName").text = config.host_name
        ET.SubElement(root, "URL").text = config.url_template
        ET.SubElement(root, "Port").text = str(config.port)
        ET.SubElement(root, "Protocol").text = config.protocol
        ET.SubElement(root, "MinLevel").text = "1"
        ET.SubElement(root, "MaxLevel").text = "23"
        ET.SubElement(root, "Projection").text = "墨卡托中国"
        ET.SubElement(root, "ImageType").text = config.img_type
        ET.SubElement(root, "ImageFormat").text = config.img_format
        ET.SubElement(root, "ImageSize").text = "256"
        
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def export_all(self, config: TileSourceConfig, base_path):
        self.export_ovmap(config, f"{base_path}.ovmap")
        self.generate_qrcode(config, f"{base_path}.png")

# ================== GUI 界面 ==================
def create_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("奥维地图图源生成器【完美版】")
    root.geometry("720x600")
    root.resizable(False, False)

    gen = OvitalMapGenerator()

    # ---------- 界面逻辑 ----------
    def select_path():
        p = filedialog.askdirectory()
        if p:
            path_var.set(p)

    def build():
        tp = template_var.get()
        if tp == "自动": tp = "卫星图"
        name = name_var.get()
        path = path_var.get()
        if not path: path = os.path.expanduser("~/Desktop")
        full = os.path.join(path, name)

        try:
            cfg = gen.create_google_source(tp)
            gen.export_all(cfg, full)
            messagebox.showinfo("成功", f"已生成：\n{full}.ovmap\n{full}.png\n\n可直接导入奥维！")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ---------- 布局 ----------
    tk.Label(root, text="奥维互动地图 图源生成工具", font=("微软雅黑", 16, "bold")).pack(pady=15)

    frame = ttk.LabelFrame(root, text="配置", padding=15)
    frame.pack(fill="x", pad=20)

    ttk.Label(frame, text="预设模板：").grid(row=0, column=0, sticky="w", pady=6)
    template_var = tk.StringVar(value="卫星图")
    ttk.Combobox(frame, textvariable=template_var, values=["卫星图", "混合图", "道路图", "地形图"], width=18, state="readonly").grid(row=0, column=1, sticky="w")

    ttk.Label(frame, text="文件名称：").grid(row=1, column=0, sticky="w", pady=6)
    name_var = tk.StringVar(value="Google卫星图")
    ttk.Entry(frame, textvariable=name_var, width=25).grid(row=1, column=1, sticky="w")

    ttk.Label(frame, text="保存位置：").grid(row=2, column=0, sticky="w", pady=6)
    path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop"))
    ttk.Entry(frame, textvariable=path_var, width=35).grid(row=2, column=1, sticky="w")
    ttk.Button(frame, text="浏览", command=select_path, width=8).grid(row=2, column=2, padx=5)

    ttk.Button(root, text="▶ 生成图源文件 + 二维码", command=build, width=35).pack(pady=15)

    tk.Label(root, text="生成后：\n① 奥维 → 自定义地图 → 导入 .ovmap 文件\n② 或直接扫描二维码", fg="gray", justify="left").pack(pady=5)

    root.mainloop()

# ================== 启动 ==================
if __name__ == "__main__":
    create_gui()
