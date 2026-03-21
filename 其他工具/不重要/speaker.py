import os
import json
import re
import sys
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import time
from collections import defaultdict

class BatchReplaceS:
    def __init__(self, root):
        self.root = root
        self.root.title("批量替换说话人(s字段)工具 - 高性能版")
        self.root.geometry("800x700")
        self.root.configure(bg='#1e1e1e')
        
        self.setup_dark_theme()
        
        # 数据
        self.script_path = ""
        self.chunk_cache = {}  # 缓存所有chunk数据 {chunk_num: {id: data}}
        self.chunk_files = []  # 所有chunk文件列表
        self.total_dialogues = 0
        
        # 块大小
        self.chunk_size = 500
        
        # 映射表
        self.mapping = {}
        
        self.create_widgets()
        
    def setup_dark_theme(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('.', 
                       background='#1e1e1e',
                       foreground='#d4d4d4',
                       fieldbackground='#252526',
                       insertcolor='#d4d4d4',
                       selectbackground='#264f78',
                       selectforeground='#d4d4d4',
                       troughcolor='#3c3c3c')
        
        style.configure('TButton',
                       background='#333333',
                       foreground='#d4d4d4',
                       borderwidth=1)
        style.map('TButton',
                 background=[('active', '#555555'), ('pressed', '#444444')])
        
        style.configure('TLabel',
                       background='#1e1e1e',
                       foreground='#d4d4d4')
        
        style.configure('TLabelframe',
                       background='#1e1e1e',
                       foreground='#d4d4d4',
                       bordercolor='#555555')
        style.configure('TLabelframe.Label',
                       background='#1e1e1e',
                       foreground='#569cd6')
        
        style.configure('TEntry',
                       fieldbackground='#252526',
                       foreground='#d4d4d4',
                       insertcolor='#d4d4d4',
                       bordercolor='#555555')
        
        style.configure('Vertical.TScrollbar',
                       background='#3c3c3c',
                       troughcolor='#1e1e1e')
    
    def create_widgets(self):
        # 控制面板
        control_frame = ttk.LabelFrame(self.root, text="项目设置", padding="10")
        control_frame.pack(fill="x", padx=10, pady=5)
        
        path_frame = ttk.Frame(control_frame)
        path_frame.pack(fill="x", pady=(0,5))
        
        ttk.Label(path_frame, text="脚本文件夹:").pack(side="left", padx=5)
        self.path_label = ttk.Label(path_frame, text="未选择", foreground="#569cd6")
        self.path_label.pack(side="left", padx=5)
        
        ttk.Button(path_frame, text="选择项目文件夹", command=self.select_project).pack(side="left", padx=5)
        ttk.Button(path_frame, text="选择脚本文件夹", command=self.select_script_folder).pack(side="left", padx=5)
        
        self.status_label = ttk.Label(control_frame, text="就绪", foreground="#6a9955")
        self.status_label.pack(anchor="w", pady=5)
        
        self.dialogue_count_label = ttk.Label(control_frame, text="总对话数: 0")
        self.dialogue_count_label.pack(anchor="w", pady=2)
        
        # 映射输入区域
        map_frame = ttk.LabelFrame(self.root, text="替换映射", padding="10")
        map_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        info_frame = ttk.Frame(map_frame)
        info_frame.pack(fill="x", pady=(0,5))
        ttk.Label(info_frame, text="说明: null=删除，[CHAPTER?-?]=章节标记(不加括号)，其他自动加【】", foreground="#858585").pack(anchor="w")
        
        btn_frame = ttk.Frame(map_frame)
        btn_frame.pack(fill="x", pady=(0,5))
        ttk.Button(btn_frame, text="从文件导入", command=self.import_mapping_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="清除映射", command=self.clear_mapping).pack(side="left", padx=5)
        
        self.map_text = scrolledtext.ScrolledText(
            map_frame,
            font=("Consolas", 10),
            height=12,
            bg='#252526',
            fg='#d4d4d4',
            insertbackground='#d4d4d4',
            selectbackground='#264f78',
            relief='flat'
        )
        self.map_text.pack(fill="both", expand=True)
        self.map_text.insert(tk.END, "# 每行格式: 对话ID: 新值\n# 示例:\n52: null\n53: 声音\n54: 雪鹰\n55: [CHAPTER1-1]\n")
        
        # 操作按钮
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(action_frame, text="开始替换 (高性能)", command=self.start_replace, width=15).pack(side="left", padx=5)
        ttk.Button(action_frame, text="仅预览", command=self.preview_replace, width=10).pack(side="left", padx=5)
        ttk.Button(action_frame, text="清除缓存", command=self.clear_cache, width=10).pack(side="left", padx=5)
        
        # 进度条
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(action_frame, variable=self.progress_var, 
                                            maximum=100, length=200, mode='determinate')
        self.progress_bar.pack(side="right", padx=10)
        
        # 结果输出区域
        log_frame = ttk.LabelFrame(self.root, text="操作日志", padding="10")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            height=10,
            bg='#252526',
            fg='#d4d4d4',
            insertbackground='#d4d4d4',
            selectbackground='#264f78',
            relief='flat'
        )
        self.log_text.pack(fill="both", expand=True)
    
    def log(self, msg, level="INFO"):
        import time
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def select_project(self):
        folder = filedialog.askdirectory(title="选择游戏根目录")
        if not folder:
            return
        common_path = os.path.join(folder, "common")
        if not os.path.exists(common_path):
            messagebox.showerror("错误", "未找到common文件夹！")
            return
        self.script_path = os.path.join(common_path, "script")
        self.path_label.config(text=f"项目: {os.path.basename(folder)}")
        self.load_all_scripts_fast()
    
    def select_script_folder(self):
        folder = filedialog.askdirectory(title="选择脚本文件夹")
        if not folder:
            return
        self.script_path = folder
        self.path_label.config(text=f"脚本: {os.path.basename(folder)}")
        self.load_all_scripts_fast()
    
    def load_all_scripts_fast(self):
        """快速加载所有脚本到内存缓存"""
        if not self.script_path or not os.path.exists(self.script_path):
            self.log("错误: 脚本文件夹不存在")
            return
        
        self.chunk_cache = {}
        self.chunk_files = []
        
        try:
            # 获取所有scriptData文件
            files = [f for f in os.listdir(self.script_path) 
                    if f.lower().startswith("scriptdata") and f.lower().endswith(".txt")]
            
            def extract_number(filename):
                match = re.search(r'(\d+)', filename)
                return int(match.group(1)) if match else 0
            
            files.sort(key=extract_number)
            self.chunk_files = files
            
            total_dialogues = 0
            self.log(f"正在加载 {len(files)} 个文件...")
            
            for i, filename in enumerate(files):
                file_path = os.path.join(self.script_path, filename)
                
                # 提取块号
                chunk_num = extract_number(filename)
                
                # 快速加载JSON
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        chunk_data = json.loads(content)
                        self.chunk_cache[chunk_num] = chunk_data
                        total_dialogues += len(chunk_data)
                        
                        # 更新进度
                        progress = (i + 1) * 100 // len(files)
                        self.progress_var.set(progress)
                        self.root.update()
                        
                except json.JSONDecodeError as e:
                    self.log(f"警告: {filename} JSON解析失败: {e}")
                    self.chunk_cache[chunk_num] = {}
                except Exception as e:
                    self.log(f"警告: 加载{filename}失败: {e}")
                    self.chunk_cache[chunk_num] = {}
            
            self.total_dialogues = total_dialogues
            self.dialogue_count_label.config(text=f"总对话数: {self.total_dialogues}")
            self.log(f"加载完成! 共 {len(self.chunk_cache)} 个块文件, {total_dialogues} 条对话")
            self.status_label.config(text="加载完成", foreground="#6a9955")
            self.progress_var.set(0)
            
        except Exception as e:
            self.log(f"加载失败: {e}")
            messagebox.showerror("错误", f"加载失败: {e}")
    
    def import_mapping_file(self):
        file_path = filedialog.askopenfilename(
            title="选择映射文件",
            filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.map_text.delete(1.0, tk.END)
            self.map_text.insert(1.0, content)
            self.log(f"已导入映射: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"读取失败: {e}")
    
    def clear_mapping(self):
        self.map_text.delete(1.0, tk.END)
        self.map_text.insert(tk.END, "# 每行格式: 对话ID: 新值\n# 示例:\n52: null\n53: 声音\n54: 雪鹰\n55: [CHAPTER1-1]\n")
        self.log("映射已清空")
    
    def clear_cache(self):
        self.chunk_cache.clear()
        self.log("缓存已清除")
        self.status_label.config(text="缓存已清除", foreground="#ffcc00")
    
    def is_chapter_marker(self, value):
        pattern = r'^\[CHAPTER\d+-\d+\]$'
        return bool(re.match(pattern, value, re.IGNORECASE))
    
    def parse_mapping(self):
        """快速解析映射"""
        text = self.map_text.get(1.0, tk.END)
        mapping = {}
        lines = text.splitlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
            
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            
            id_str = parts[0].strip()
            value_str = parts[1].strip()
            
            try:
                dialogue_id = int(id_str)
            except ValueError:
                self.log(f"警告: 无效ID '{id_str}'")
                continue
            
            # 处理值
            if value_str.lower() == 'null':
                value = None
            else:
                # 去掉引号
                if (value_str.startswith('"') and value_str.endswith('"')) or \
                   (value_str.startswith("'") and value_str.endswith("'")):
                    value_str = value_str[1:-1]
                
                # 判断类型
                if self.is_chapter_marker(value_str):
                    value = value_str
                elif value_str.startswith('【') and value_str.endswith('】'):
                    value = value_str
                else:
                    value = f"【{value_str}】"
            
            mapping[dialogue_id] = value
        
        return mapping
    
    def preview_replace(self):
        """快速预览"""
        if not self.chunk_cache:
            messagebox.showwarning("警告", "请先加载脚本数据")
            return
        
        self.mapping = self.parse_mapping()
        if not self.mapping:
            messagebox.showinfo("提示", "没有有效的映射条目")
            return
        
        # 快速统计
        changes = []
        found_count = 0
        
        for dialogue_id, new_s in self.mapping.items():
            key = str(dialogue_id)
            chunk_num = (dialogue_id - 1) // self.chunk_size + 1
            
            if chunk_num in self.chunk_cache:
                chunk_data = self.chunk_cache[chunk_num]
                if key in chunk_data:
                    found_count += 1
                    old_s = chunk_data[key].get('s', None)
                    if old_s != new_s:
                        changes.append((dialogue_id, old_s, new_s))
        
        # 显示预览窗口
        preview_win = tk.Toplevel(self.root)
        preview_win.title("替换预览")
        preview_win.geometry("600x500")
        preview_win.configure(bg='#1e1e1e')
        
        preview_text = scrolledtext.ScrolledText(
            preview_win,
            font=("Consolas", 10),
            bg='#252526',
            fg='#d4d4d4',
            insertbackground='#d4d4d4',
            selectbackground='#264f78',
            relief='flat'
        )
        preview_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        preview_text.insert(tk.END, f"映射总数: {len(self.mapping)}\n")
        preview_text.insert(tk.END, f"找到对话: {found_count}\n")
        preview_text.insert(tk.END, f"将修改: {len(changes)} 条对话\n\n")
        
        for dialogue_id, old_s, new_s in changes[:100]:  # 最多显示100条
            if new_s is None:
                preview_text.insert(tk.END, f"ID {dialogue_id}: 删除 '{old_s}'\n")
            else:
                preview_text.insert(tk.END, f"ID {dialogue_id}: '{old_s}' -> '{new_s}'\n")
        
        if len(changes) > 100:
            preview_text.insert(tk.END, f"\n... 还有 {len(changes)-100} 条未显示")
        
        ttk.Button(preview_win, text="关闭", command=preview_win.destroy).pack(pady=10)
    
    def start_replace(self):
        """高性能批量替换"""
        if not self.chunk_cache:
            messagebox.showwarning("警告", "请先加载脚本数据")
            return
        
        self.mapping = self.parse_mapping()
        if not self.mapping:
            messagebox.showinfo("提示", "没有有效的映射条目")
            return
        
        if not messagebox.askyesno("确认", f"将修改 {len(self.mapping)} 条对话，是否继续？\n建议先预览。"):
            return
        
        # 备份
        if messagebox.askyesno("备份", "是否在修改前备份所有文件？"):
            self.backup_files()
        
        # 执行替换（直接修改内存缓存）
        self.log("开始执行替换...")
        changes_count = 0
        affected_chunks = set()
        
        # 按块分组，提高效率
        chunk_updates = defaultdict(list)
        
        for dialogue_id, new_s in self.mapping.items():
            key = str(dialogue_id)
            chunk_num = (dialogue_id - 1) // self.chunk_size + 1
            
            if chunk_num in self.chunk_cache:
                chunk_data = self.chunk_cache[chunk_num]
                if key in chunk_data:
                    old_s = chunk_data[key].get('s', None)
                    
                    # 只有值不同才修改
                    if old_s != new_s:
                        if new_s is None:
                            if 's' in chunk_data[key]:
                                del chunk_data[key]['s']
                                changes_count += 1
                                chunk_updates[chunk_num].append(dialogue_id)
                        else:
                            chunk_data[key]['s'] = new_s
                            changes_count += 1
                            chunk_updates[chunk_num].append(dialogue_id)
        
        if changes_count == 0:
            self.log("没有需要修改的内容")
            return
        
        # 保存修改的块
        self.log(f"修改了 {changes_count} 条对话，影响 {len(chunk_updates)} 个块文件")
        self.log("开始保存文件...")
        
        saved_count = 0
        total_chunks = len(chunk_updates)
        
        for i, (chunk_num, updated_ids) in enumerate(chunk_updates.items()):
            chunk_data = self.chunk_cache[chunk_num]
            
            # 保存到文件
            chunk_file = os.path.join(self.script_path, f"scriptData{chunk_num}.txt")
            try:
                # 排序后保存
                sorted_data = {}
                for id_key in sorted(chunk_data.keys(), key=lambda x: int(x)):
                    sorted_data[id_key] = chunk_data[id_key]
                
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    json.dump(sorted_data, f, ensure_ascii=False, indent=2)
                
                saved_count += 1
                
                # 更新进度
                progress = (i + 1) * 100 // total_chunks
                self.progress_var.set(progress)
                self.root.update()
                
                self.log(f"已保存块 {chunk_num} (修改了 {len(updated_ids)} 条)")
                
            except Exception as e:
                self.log(f"保存块 {chunk_num} 失败: {e}")
        
        self.log(f"替换完成！共修改 {changes_count} 条对话，保存 {saved_count}/{total_chunks} 个文件")
        self.status_label.config(text="替换完成", foreground="#6a9955")
        self.progress_var.set(0)
        
        # 显示统计
        messagebox.showinfo("完成", f"替换完成！\n修改对话: {changes_count} 条\n保存文件: {saved_count} 个")
    
    def backup_files(self):
        """备份所有脚本文件"""
        if not self.script_path:
            return
        
        backup_folder = os.path.join(self.script_path, "backup_" + time.strftime("%Y%m%d_%H%M%S"))
        
        try:
            os.makedirs(backup_folder)
            
            for filename in self.chunk_files:
                src = os.path.join(self.script_path, filename)
                dst = os.path.join(backup_folder, filename)
                
                with open(src, 'rb') as fs, open(dst, 'wb') as fd:
                    fd.write(fs.read())
            
            self.log(f"备份完成: {backup_folder}")
            self.log(f"备份了 {len(self.chunk_files)} 个文件")
            
        except Exception as e:
            self.log(f"备份失败: {e}")
            if not messagebox.askyesno("继续", "备份失败，是否继续替换？"):
                return False
        
        return True

def main():
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    root = tk.Tk()
    app = BatchReplaceS(root)
    root.mainloop()

if __name__ == "__main__":
    main()