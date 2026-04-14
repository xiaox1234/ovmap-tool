import tkinter as tk
from tkinter import ttk, messagebox
import qrcode
import os
from urllib.parse import urlparse

# ================== 核心功能 ==================
def parse_map_url(url):
    """自动解析URL，拆分域名、路径、端口"""
    try:
        parsed = urlparse(url)
        protocol = parsed.scheme
        host = parsed.netloc
        path = parsed.path
        query = parsed.query
        if query:
            path += "?" + query

        port = 443 if protocol == "https" else 80
        return host, path, port, protocol
    except:
        return "", "", 80, "http"

def generate_qr(url):
    """生成二维码并保存到桌面"""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    save_path = os.path.join(desktop, "奥维图源二维码.png")
    img.save(save_path)
    return save_path

def build_config_text(name, host, path, port, protocol):
    """生成奥维完整配置文本"""
    return f"""=== 奥维自定义地图配置 ===
名称：{name}
协议：{protocol.upper()}
服务器域名：{host}
端口：{port}
URL路径：{path}
地图类型：影像地图
最大缩放：20
投影：墨卡托全球
"""

# ================== 界面操作 ==================
def make_config():
    url = entry_url.get().strip()
    name = entry_name.get().strip() or "自定义图源"

    if not url or not all(k in url for k in ["{x}", "{y}", "{z}"]):
        messagebox.showerror("错误", "URL必须包含 {x} {y} {z}")
        return

    host, path, port, protocol = parse_map_url(url)
    config = build_config_text(name, host, path, port, protocol)

    text_result.delete(1.0, tk.END)
    text_result.insert(tk.END, config)

    # 复制到剪贴板
    root.clipboard_clear()
    root.clipboard_append(config)

def make_qr_code():
    url = entry_url.get().strip()
    if not url:
        messagebox.showwarning("提示", "请先输入URL")
        return
    path = generate_qr(url)
    messagebox.showinfo("完成", f"二维码已保存到桌面\n{path}")

# ================== 主界面 ==================
root = tk.Tk()
root.title("奥维图源自定义工具 - 直接输入URL")
root.geometry("620x480")
root.resizable(False, False)

# 标题
tk.Label(root, text="奥维地图图源生成器", font=("微软雅黑", 14, "bold")).pack(pady=10)

# 输入框
frame_input = tk.Frame(root)
frame_input.pack(pady=5, fill="x", padx=20)

tk.Label(frame_input, text="地图名称：", font=("微软雅黑", 10)).grid(row=0, column=0, sticky="w")
entry_name = tk.Entry(frame_input, width=30, font=("微软雅黑", 10))
entry_name.grid(row=0, column=1, padx=5)
entry_name.insert(0, "谷歌卫星图源")

tk.Label(frame_input, text="图源URL：", font=("微软雅黑", 10)).grid(row=1, column=0, sticky="w")
entry_url = tk.Entry(frame_input, width=50, font=("微软雅黑", 10))
entry_url.grid(row=1, column=1, padx=5)
entry_url.insert(0, "https://mt0.google.com/vt?lyrs=s&x={x}&y={y}&z={z}")

# 按钮
frame_btn = tk.Frame(root)
frame_btn.pack(pady=10)
tk.Button(frame_btn, text="🔥 生成奥维配置", command=make_config, width=18, bg="#2196F3", fg="white").grid(row=0, column=0, padx=5)
tk.Button(frame_btn, text="📷 生成二维码", command=make_qr_code, width=18, bg="#4CAF50", fg="white").grid(row=0, column=1, padx=5)

# 结果显示
tk.Label(root, text="生成的配置（已自动复制）：", font=("微软雅黑", 10)).pack(padx=20, anchor="w")
text_result = tk.Text(root, height=12, font=("微软雅黑", 10))
text_result.pack(padx=20, pady=5, fill="both", expand=True)

root.mainloop()
