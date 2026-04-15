#!/usr/bin/env python3
"""
奥维地图图源自动生成工具（带自定义保存路径+中文模板版）
"""

import os
import sys
import re
import json
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET
import qrcode
import requests

# ================== 关键：EXE 路径兼容 + 控制台修复 ==================
def resource_path(relative_path):
    """获取资源绝对路径，兼容开发和PyInstaller打包环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 修复--windowed打包后argparse打印崩溃问题
if getattr(sys, 'frozen', False):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# ================== 修复selenium导入 ==================
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException
except ImportError:
    webdriver = None
    Service = None
    Options = None


# ---------- 数据结构定义 ----------
@dataclass
class TileSourceConfig:
    map_id: int = 300
    map_name: str = "自定义图源"
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


# ---------- URL模式识别 ----------
class TileURLParser:
    XYZ_PATTERNS = [
        (r'/(\d+)/(\d+)/(\d+)\.(jpg|png|jpeg|webp)', '/{$z}/{$x}/{$y}.{ext}'),
        (r'x=(\d+)&y=(\d+)&z=(\d+)', 'x={$x}&y={$y}&z={$z}'),
        (r'/tile/(\d+)/(\d+)/(\d+)', '/tile/{$z}/{$x}/{$y}'),
        (r'/vt\?lyrs=([^&]+)&x=(\d+)&y=(\d+)&z=(\d+)', '/vt?lyrs={lyrs}&x={$x}&y={$y}&z={$z}'),
        (r'/maps/vt\?lyrs=([^&]+)&x=(\d+)&y=(\d+)&z=(\d+)', '/maps/vt?lyrs={lyrs}&x={$x}&y={$y}&z={$z}'),
        (r'/(\d+)/(\d+)/(\d+)\.(jpg|png)', '/{$z}/{$x}/{tms_y}.{ext}'),
    ]
    
    @classmethod
    def parse_url(cls, url: str) -> Optional[Tuple[str, Dict]]:
        for pattern, template in cls.XYZ_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                groups = match.groups()
                params = {}
                
                if 'lyrs' in template:
                    params['lyrs'] = groups[0]
                    params['x'], params['y'], params['z'] = groups[1:4]
                elif 'ext' in template:
                    params['z'], params['x'], params['y'], params['ext'] = groups
                else:
                    params['z'], params['x'], params['y'] = groups[-3:]
                
                filled_template = template
                if '{lyrs}' in filled_template:
                    filled_template = filled_template.replace('{lyrs}', params.get('lyrs', 's'))
                if '{ext}' in filled_template:
                    filled_template = filled_template.replace('{ext}', params.get('ext', 'jpg'))
                
                return filled_template, params
        
        return None


# ---------- 网络请求拦截器（修复驱动加载） ----------
class NetworkInterceptor:
    def __init__(self):
        self.captured_urls: List[str] = []
        self.driver = None
    
    def _setup_driver(self) -> webdriver.Chrome:
        if webdriver is None or Service is None or Options is None:
            raise ImportError("selenium未安装，无法使用自动抓取功能")
            
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        driver_path = resource_path("chromedriver.exe")
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def capture_from_url(self, target_url: str, wait_time: int = 5) -> List[str]:
        self.driver = self._setup_driver()
        self.captured_urls.clear()
        
        try:
            self.driver.get(target_url)
            time.sleep(wait_time)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            logs = self.driver.get_log('performance')
            for entry in logs:
                try:
                    message = json.loads(entry['message'])['message']
                    if message['method'] == 'Network.responseReceived':
                        url = message['params']['response']['url']
                        if self._is_tile_url(url):
                            self.captured_urls.append(url)
                except Exception as e:
                    continue
            
        except WebDriverException as e:
            print(f"❌ 浏览器驱动错误: {e}")
        except Exception as e:
            print(f"❌ 捕获过程中出错: {e}")
        finally:
            if self.driver:
                self.driver.quit()
        
        return self.captured_urls
    
    def _is_tile_url(self, url: str) -> bool:
        tile_keywords = ['vt', 'lyrs', 'tile', 'google', 'x=', 'y=', 'z=', '.jpg', '.png']
        url_lower = url.lower()
        has_keyword = any(kw in url_lower for kw in tile_keywords)
        has_coords = bool(re.search(r'[?&/][xyz]=?\d+', url_lower))
        return has_keyword and has_coords


# ---------- 奥维图源生成器 ----------
class OvitalMapGenerator:
    GOOGLE_TEMPLATES = {
        "卫星图": {
            "name": "Google卫星图",
            "url": "/maps/vt?lyrs=s&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "img_type": "影像地图"
        },
        "混合图": {
            "name": "Google混合图",
            "url": "/maps/vt?lyrs=s,h&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "img_type": "影像地图"
        },
        "道路图": {
            "name": "Google道路图",
            "url": "/maps/vt?lyrs=m&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "img_type": "普通地图"
        },
        "地形图": {
            "name": "Google地形图",
            "url": "/maps/vt?lyrs=t&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}",
            "img_type": "普通地图"
        }
    }
    
    def __init__(self):
        self.configs: List[TileSourceConfig] = []
    
    def create_from_url(self, url_template: str, host_name: str, map_name: str = "自定义图源", map_id: int = 300) -> TileSourceConfig:
        config = TileSourceConfig(
            map_id=map_id,
            map_name=map_name,
            host_name=host_name,
            url_template=url_template,
            protocol="https" if host_name.startswith("https") else "http"
        )
        if url_template.endswith('.png'):
            config.img_format = 'png'
        elif url_template.endswith('.jpg') or url_template.endswith('.jpeg'):
            config.img_format = 'jpg'
        self.configs.append(config)
        return config
    
    def create_google_source(self, template_key: str = "卫星图"):
        template = self.GOOGLE_TEMPLATES.get(template_key, self.GOOGLE_TEMPLATES["卫星图"])
        config = TileSourceConfig(
            map_name=template["name"],
            host_name="gac-geo.googlecnapps.cn",
            url_template=template["url"],
            img_type=template["img_type"],
            protocol="http",
            max_level=23,
            proj_type="墨卡托中国",
            img_size=256
        )
        self.configs.append(config)
        return config
    
    def export_ovmap(self, config: TileSourceConfig, filepath: str):
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
        ET.SubElement(root, "Overlay").text = config.overlay
        ET.SubElement(root, "BaseMap").text = config.basemap
        if config.referer:
            ET.SubElement(root, "Referer").text = config.referer
        if config.cookies:
            ET.SubElement(root, "Cookies").text = config.cookies
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
    
    def export_json(self, config: TileSourceConfig, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)
    
    def generate_qrcode(self, config: TileSourceConfig, filepath: str):
        qr_data = f"ovital://addmap?name={config.map_name}&host={config.host_name}&url={config.url_template}&proj={config.proj_type}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filepath)
    
    def export_all(self, config: TileSourceConfig, base_filename: str):
        output_dir = os.path.dirname(base_filename)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.export_ovmap(config, f"{base_filename}.ovmap")
        self.export_json(config, f"{base_filename}.json")
        self.generate_qrcode(config, f"{base_filename}.png")


# ---------- 主程序 ----------
class OvitalMapTool:
    def __init__(self):
        self.parser = TileURLParser()
        self.generator = OvitalMapGenerator()
        self.interceptor = NetworkInterceptor()
    
    def process_url(self, target_url: str, output_path: str):
        captured = self.interceptor.capture_from_url(target_url)
        
        if captured:
            for url in captured[:5]:
                result = self.parser.parse_url(url)
                if result:
                    template, params = result
                    parsed = urllib.parse.urlparse(url)
                    host_name = parsed.netloc
                    config = self.generator.create_from_url(template, host_name, f"自动抓取_{host_name}")
                    self.generator.export_all(config, output_path)
                    return config
        
        config = self.generator.create_google_source("卫星图")
        self.generator.export_all(config, output_path)
        return config
    
    def create_from_manual_input(self, host_name: str, url_template: str, map_name: str, output_path: str):
        config = self.generator.create_from_url(url_template, host_name, map_name)
        self.generator.export_all(config, output_path)
        return config


# ---------- 图形界面（新增选择保存路径 + 中文模板） ----------
def create_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        messagebox.showerror("错误", "tkinter不可用，无法启动图形界面")
        return
    
    class OvitalMapGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("奥维地图图源生成器")
            self.root.geometry("750x650")
            self.root.resizable(False, False)
            self.tool = OvitalMapTool()
            self._create_widgets()
        
        def _create_widgets(self):
            # 标题
            title = ttk.Label(self.root, text="奥维地图图源自动生成工具", font=('微软雅黑', 16, 'bold'))
            title.pack(pady=20)
            
            # 输入区域
            input_frame = ttk.LabelFrame(self.root, text="输入配置", padding=10)
            input_frame.pack(fill='x', padx=20, pady=10)
            
            # 1. 目标网站URL
            ttk.Label(input_frame, text="目标网站URL:").grid(row=0, column=0, sticky='w', pady=5)
            self.url_entry = ttk.Entry(input_frame, width=55)
            self.url_entry.grid(row=0, column=1, padx=5, pady=5, columnspan=2)
            self.url_entry.insert(0, "https://www.google.com/maps")
            
            # 2. 输出文件名
            ttk.Label(input_frame, text="输出文件名:").grid(row=1, column=0, sticky='w', pady=5)
            self.output_entry = ttk.Entry(input_frame, width=30)
            self.output_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
            self.output_entry.insert(0, "ovital_map_source")
            
            # 3. 保存路径
            ttk.Label(input_frame, text="文件保存位置:").grid(row=2, column=0, sticky='w', pady=5)
            self.path_entry = ttk.Entry(input_frame, width=40)
            self.path_entry.grid(row=2, column=1, sticky='w', padx=5, pady=5)
            default_path = os.path.join(os.path.expanduser("~"), "Desktop")
            self.path_entry.insert(0, default_path)
            ttk.Button(input_frame, text="浏览...", command=self._browse_path, width=8).grid(row=2, column=2, padx=5, pady=5)
            
            # 4. 预设模板（中文）
            ttk.Label(input_frame, text="预设模板:").grid(row=3, column=0, sticky='w', pady=5)
            self.template_var = tk.StringVar(value="自动")
            template_combo = ttk.Combobox(
                input_frame,
                textvariable=self.template_var,
                values=["自动", "卫星图", "混合图", "道路图", "地形图"],
                width=15,
                state="readonly"
            )
            template_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)
            template_combo.set("自动")
            
            # 按钮区域
            btn_frame = ttk.Frame(self.root)
            btn_frame.pack(pady=20)
            ttk.Button(btn_frame, text="自动抓取并生成", command=self.process_auto, width=20).pack(side='left', padx=10)
            ttk.Button(btn_frame, text="手动配置", command=self.open_manual_config, width=20).pack(side='left', padx=10)
            ttk.Button(btn_frame, text="使用Google模板", command=self.use_google_template, width=20).pack(side='left', padx=10)
            
            # 日志区域
            log_frame = ttk.LabelFrame(self.root, text="运行日志", padding=5)
            log_frame.pack(fill='both', expand=True, padx=20, pady=10)
            self.log_text = tk.Text(log_frame, height=15, width=85)
            scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
            self.log_text.configure(yscrollcommand=scrollbar.set)
            self.log_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
        
        def _browse_path(self):
            path = filedialog.askdirectory(title="选择文件保存位置", initialdir=self.path_entry.get())
            if path:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, path)
        
        def log(self, message):
            self.log_text.insert('end', message + '\n')
            self.log_text.see('end')
            self.root.update()
        
        def _get_full_output_path(self):
            save_dir = self.path_entry.get().strip()
            filename = self.output_entry.get().strip() or "ovital_map_source"
            if not save_dir:
                save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            return os.path.join(save_dir, filename)
        
        def process_auto(self):
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showerror("错误", "请输入目标网站URL")
                return
            output_path = self._get_full_output_path()
            self.log(f"开始分析: {url}")
            self.log(f"文件将保存至: {output_path}.*")
            try:
                config = self.tool.process_url(url, output_path)
                self.log(f"✓ 成功生成图源配置！")
                self.log(f"  地图名称: {config.map_name}")
                self.log(f"  主机名: {config.host_name}")
                self.log(f"  URL模板: {config.url_template}")
                self.log(f"✓ 文件已保存: {output_path}.ovmap, {output_path}.json, {output_path}.png")
                messagebox.showinfo("成功", f"图源配置已生成！\n保存位置: {output_path}.ovmap")
            except Exception as e:
                self.log(f"✗ 错误: {str(e)}")
                messagebox.showerror("错误", str(e))
        
        def open_manual_config(self):
            manual_window = tk.Toplevel(self.root)
            manual_window.title("手动配置")
            manual_window.geometry("550x550")
            frame = ttk.Frame(manual_window, padding=10)
            frame.pack(fill='both', expand=True)
            fields = [
                ("地图名称:", "map_name", "自定义图源"),
                ("主机名:", "host_name", "gac-geo.googlecnapps.cn"),
                ("URL模板:", "url_template", "/maps/vt?lyrs=s&gl=CN&hl=zh-CN&x={$x}&y={$y}&z={$z}"),
                ("最大级别:", "max_level", "23"),
                ("投影类型:", "proj_type", "墨卡托中国"),
                ("图片类型:", "img_type", "影像地图"),
                ("图片格式:", "img_format", "jpg"),
                ("端口:", "port", "443"),
                ("协议:", "protocol", "https"),
            ]
            entries = {}
            for i, (label, key, default) in enumerate(fields):
                ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', pady=5)
                entry = ttk.Entry(frame, width=45)
                entry.grid(row=i, column=1, padx=5, pady=5)
                entry.insert(0, default)
                entries[key] = entry
            def save_manual():
                try:
                    config = TileSourceConfig(
                        map_name=entries["map_name"].get(),
                        host_name=entries["host_name"].get(),
                        url_template=entries["url_template"].get(),
                        max_level=int(entries["max_level"].get()),
                        proj_type=entries["proj_type"].get(),
                        img_type=entries["img_type"].get(),
                        img_format=entries["img_format"].get(),
                        port=int(entries["port"].get()),
                        protocol=entries["protocol"].get()
                    )
                    output_path = self._get_full_output_path()
                    self.tool.generator.export_all(config, output_path)
                    self.log(f"✓ 手动配置已保存: {output_path}.ovmap")
                    messagebox.showinfo("成功", f"配置已保存: {output_path}.ovmap")
                    manual_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", str(e))
            ttk.Button(frame, text="保存配置", command=save_manual).grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        def use_google_template(self):
            template = self.template_var.get()
            if template == "自动":
                template = "卫星图"
            config = self.tool.generator.create_google_source(template)
            output_path = self._get_full_output_path()
            self.tool.generator.export_all(config, output_path)
            self.log(f"✓ 使用Google模板生成: {template}")
            self.log(f"✓ 文件已保存: {output_path}.ovmap")
            messagebox.showinfo("成功", f"Google图源已生成: {output_path}.ovmap")
    
    root = tk.Tk()
    app = OvitalMapGUI(root)
    root.mainloop()


# ---------- 命令行入口 ----------
def main():
    if getattr(sys, 'frozen', False):
        create_gui()
        return
    
    import argparse
    parser = argparse.ArgumentParser(description="奥维地图图源自动生成工具")
    parser.add_argument('--gui', '-g', action='store_true', help='启动图形界面', default=True)
    args = parser.parse_args()
    create_gui()

if __name__ == "__main__":
    main()
