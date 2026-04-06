import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image

class ImageProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("PNG图片批量处理器")
        self.root.geometry("500x300")
        self.root.resizable(False, False)

        # 变量
        self.folder_path = tk.StringVar()

        # 界面布局
        self.create_widgets()

    def create_widgets(self):
        # 文件夹选择区域
        frame_dir = tk.Frame(self.root, padx=10, pady=10)
        frame_dir.pack(fill=tk.X)

        tk.Label(frame_dir, text="文件夹路径:").pack(side=tk.LEFT)
        entry_dir = tk.Entry(frame_dir, textvariable=self.folder_path, width=40)
        entry_dir.pack(side=tk.LEFT, padx=5)
        btn_browse = tk.Button(frame_dir, text="浏览", command=self.browse_folder)
        btn_browse.pack(side=tk.LEFT)

        # 处理按钮
        btn_process = tk.Button(self.root, text="开始处理", command=self.process_images, width=20, height=2)
        btn_process.pack(pady=20)

        # 进度条
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)

        # 状态标签
        self.status_label = tk.Label(self.root, text="请选择文件夹", fg="gray")
        self.status_label.pack(pady=5)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.status_label.config(text=f"已选择: {folder}", fg="green")

    def trim_transparent_border(self, img):
        """
        去除四周透明像素（仅对RGBA模式有效）
        """
        if img.mode == 'RGBA':
            # 提取Alpha通道
            alpha = img.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                return img.crop(bbox)
        return img

    def resize_if_needed(self, img):
        """
        如果图片宽度>310 或 高度>1000，则等比缩放到不超过这两个值
        """
        width, height = img.size
        max_width = 310
        max_height = 1000

        if width > max_width or height > max_height:
            # 计算缩放比例（取最小的限制比例）
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            # 使用LANCZOS重采样，保证高质量缩放
            img = img.resize((new_width, new_height), Image.LANCZOS)
        return img

    def process_images(self):
        folder = self.folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("错误", "请先选择一个有效的文件夹！")
            return

        # 获取所有PNG文件
        png_files = [f for f in os.listdir(folder) if f.lower().endswith('.png')]
        if not png_files:
            messagebox.showinfo("提示", "该文件夹中没有PNG图片文件。")
            return

        # 用户确认
        confirm = messagebox.askyesno("确认", f"将在文件夹\n{folder}\n中处理 {len(png_files)} 个PNG文件。\n\n操作将覆盖原文件，是否继续？")
        if not confirm:
            return

        # 初始化进度条
        self.progress['maximum'] = len(png_files)
        self.progress['value'] = 0

        success_count = 0
        error_count = 0

        for idx, filename in enumerate(png_files, 1):
            filepath = os.path.join(folder, filename)
            self.status_label.config(text=f"正在处理: {filename}")
            self.root.update_idletasks()

            try:
                with Image.open(filepath) as img:
                    # 1. 去除透明边框
                    img = self.trim_transparent_border(img)
                    # 2. 缩放
                    img = self.resize_if_needed(img)
                    # 保存（覆盖原文件）
                    img.save(filepath, format='PNG')
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"处理失败: {filename}, 错误: {e}")

            # 更新进度条
            self.progress['value'] = idx
            self.root.update_idletasks()

        # 处理完成
        self.status_label.config(text="处理完成")
        messagebox.showinfo("完成", f"处理完成！\n成功: {success_count} 个\n失败: {error_count} 个")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageProcessor(root)
    root.mainloop()