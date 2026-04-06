import os
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from collections import Counter
import threading
import copy  # 用于深拷贝

def split_character_name(name):
    """将立绘名称拆分为 (主体, 后缀)，后缀可能是 '_数字' 或空字符串"""
    if not name:
        return '', ''
    match = re.match(r'^(.*?)(_\d+)?$', name)
    if match:
        base = match.group(1) or ''
        suffix = match.group(2) or ''
        return base, suffix
    return name, ''

def extract_base_name(name):
    """仅提取主体部分"""
    base, _ = split_character_name(name)
    return base

class CharacterBatchRenameTool:
    def __init__(self, root):
        self.root = root
        self.root.title("立绘批量重命名工具（仅替换主体，保留后缀）")
        self.root.geometry("900x700")
        self.root.configure(bg='#1e1e1e')

        # 数据存储
        self.script_path = ""
        self.script_files = []          # 所有脚本文件的完整路径
        self.all_data = {}               # 合并后的所有对话数据 {id: {...}}
        self.character_stats = Counter() # 立绘主体 -> 出现次数
        self.modified = False

        # 历史记录
        self.history = []                # 存储每次替换前的 all_data 快照
        self.history_limit = 20          # 最大历史记录数

        self.create_widgets()
        self.setup_styles()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background='#1e1e1e', foreground='#d4d4d4',
                        fieldbackground='#252526', selectbackground='#264f78')
        style.configure('TButton', background='#333333', foreground='#d4d4d4')
        style.map('TButton', background=[('active', '#555555')])
        style.configure('TLabel', background='#1e1e1e', foreground='#d4d4d4')
        style.configure('TLabelframe', background='#1e1e1e', foreground='#d4d4d4')
        style.configure('TEntry', fieldbackground='#252526', foreground='#d4d4d4')
        style.configure('TCombobox', fieldbackground='#252526', foreground='#d4d4d4')

    def create_widgets(self):
        # 顶部框架：选择文件夹
        top_frame = ttk.LabelFrame(self.root, text="脚本文件夹", padding=10)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(top_frame, textvariable=self.path_var, width=60)
        path_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)

        ttk.Button(top_frame, text="浏览...", command=self.select_folder).pack(side="left", padx=2)
        ttk.Button(top_frame, text="加载脚本", command=self.load_scripts_thread).pack(side="left", padx=2)

        # 主内容区域：左右分栏
        main_panel = ttk.Frame(self.root)
        main_panel.pack(fill="both", expand=True, padx=10, pady=5)

        # 左侧：立绘列表
        left_frame = ttk.LabelFrame(main_panel, text="立绘主体统计（已忽略 _1/_2 等后缀）", padding=5)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0,5))

        # 搜索框
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill="x", pady=5)
        ttk.Label(search_frame, text="筛选:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.bind('<KeyRelease>', self.filter_list)

        # 立绘列表（带滚动条）
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.character_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 10),
            bg='#252526',
            fg='#d4d4d4',
            selectbackground='#264f78',
            selectforeground='#ffffff',
            relief='flat'
        )
        self.character_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.character_listbox.yview)

        # 双击列表项自动填充到“旧名称”输入框
        self.character_listbox.bind('<Double-Button-1>', self.on_listbox_double_click)

        # 右侧：替换操作
        right_frame = ttk.LabelFrame(main_panel, text="批量替换（仅替换主体，保留后缀）", padding=10)
        right_frame.pack(side="right", fill="y", padx=(5,0))

        ttk.Label(right_frame, text="旧主体名称:").grid(row=0, column=0, sticky="w", pady=5)
        self.old_name_var = tk.StringVar()
        old_entry = ttk.Entry(right_frame, textvariable=self.old_name_var, width=25)
        old_entry.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(right_frame, text="新主体名称:").grid(row=1, column=0, sticky="w", pady=5)
        self.new_name_var = tk.StringVar()
        new_entry = ttk.Entry(right_frame, textvariable=self.new_name_var, width=25)
        new_entry.grid(row=1, column=1, pady=5, padx=5)

        # 替换选项
        self.match_case_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right_frame, text="区分大小写", variable=self.match_case_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Label(right_frame, text="替换预览:").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10,0))
        self.preview_text = scrolledtext.ScrolledText(
            right_frame, width=30, height=8,
            bg='#252526', fg='#d4d4d4', insertbackground='#d4d4d4',
            font=("Consolas", 9)
        )
        self.preview_text.grid(row=4, column=0, columnspan=2, pady=5)
        self.preview_text.insert('1.0', "点击“预览替换”查看影响\n")
        self.preview_text.config(state='disabled')

        btn_frame = ttk.Frame(right_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="预览替换", command=self.preview_replace).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="执行替换", command=self.execute_replace).pack(side="left", padx=2)

        # 底部状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side="bottom", fill="x", padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="就绪", foreground="#6a9955")
        self.status_label.pack(side="left")

        self.modified_label = ttk.Label(status_frame, text="", foreground="#ffcc00")
        self.modified_label.pack(side="right")

        ttk.Button(status_frame, text="保存所有修改", command=self.save_all).pack(side="right", padx=5)
        ttk.Button(status_frame, text="撤回", command=self.undo).pack(side="right", padx=5)

        # 初始化列表（刚启动时为空，设为 normal 以允许交互）
        self.character_listbox.config(state='normal')
        self.character_listbox.insert(tk.END, "请先加载脚本")

    def select_folder(self):
        folder = filedialog.askdirectory(title="选择包含 scriptData*.txt 的文件夹")
        if folder:
            self.script_path = folder
            self.path_var.set(folder)
            self.status_label.config(text=f"已选择文件夹: {folder}", foreground="#569cd6")

    def load_scripts_thread(self):
        """在子线程中加载脚本，避免界面卡顿"""
        if not self.script_path:
            messagebox.showwarning("警告", "请先选择脚本文件夹")
            return

        self.status_label.config(text="正在加载脚本...", foreground="#569cd6")
        self.character_listbox.config(state='normal')
        self.character_listbox.delete(0, tk.END)
        self.character_listbox.insert(tk.END, "加载中，请稍候...")
        # 保持 normal 状态，以便加载完成后用户可点击
        self.modified = False
        self.modified_label.config(text="")
        # 清空历史
        self.history.clear()

        thread = threading.Thread(target=self.load_scripts, daemon=True)
        thread.start()

    def load_scripts(self):
        """实际加载脚本的函数（在子线程运行）"""
        try:
            # 查找所有 scriptData*.txt 文件
            script_files = []
            for f in os.listdir(self.script_path):
                if f.lower().startswith("scriptdata") and f.lower().endswith(".txt"):
                    script_files.append(os.path.join(self.script_path, f))

            if not script_files:
                self.root.after(0, lambda: messagebox.showwarning("警告", "未找到 scriptData*.txt 文件"))
                self.root.after(0, lambda: self.status_label.config(text="未找到脚本文件", foreground="#ff6666"))
                return

            script_files.sort()  # 按文件名排序
            self.script_files = script_files

            all_data = {}
            char_counter = Counter()

            total_files = len(script_files)
            for idx, file_path in enumerate(script_files):
                # 更新状态
                self.root.after(0, lambda i=idx+1, t=total_files: self.status_label.config(
                    text=f"正在加载 {i}/{t}: {os.path.basename(file_path)}", foreground="#569cd6"))

                # 尝试多种编码读取
                content = None
                for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                if content is None:
                    print(f"无法读取文件: {file_path}")
                    continue

                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败 {file_path}: {e}")
                    continue

                # 合并数据，并统计立绘主体
                for key, value in data.items():
                    all_data[key] = value
                    if 'c' in value and value['c']:
                        base = extract_base_name(value['c'])
                        char_counter[base] += 1

            # 更新界面数据
            self.root.after(0, lambda: self._on_load_complete(all_data, char_counter))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"加载失败: {str(e)}"))
            self.root.after(0, lambda: self.status_label.config(text="加载失败", foreground="#ff6666"))

    def _on_load_complete(self, all_data, char_counter):
        """加载完成后更新界面"""
        self.all_data = all_data
        self.character_stats = char_counter

        # 更新列表（保持 normal 状态）
        self.character_listbox.config(state='normal')
        self.character_listbox.delete(0, tk.END)
        if char_counter:
            # 按出现次数降序显示
            for name, count in sorted(char_counter.items(), key=lambda x: (-x[1], x[0])):
                self.character_listbox.insert(tk.END, f"{name}  ({count} 次)")
        else:
            self.character_listbox.insert(tk.END, "未找到任何立绘名称")
        # 保持 normal 状态，允许用户双击

        self.status_label.config(text=f"加载完成，共 {len(all_data)} 条对话，{len(char_counter)} 个不同立绘主体", foreground="#6a9955")
        self.modified = False
        self.modified_label.config(text="")

    def filter_list(self, event=None):
        """根据搜索框内容过滤立绘列表"""
        search = self.search_var.get().lower()
        self.character_listbox.config(state='normal')
        self.character_listbox.delete(0, tk.END)

        if not self.character_stats:
            self.character_listbox.insert(tk.END, "暂无数据")
        else:
            for name, count in sorted(self.character_stats.items(), key=lambda x: (-x[1], x[0])):
                if not search or search in name.lower():
                    self.character_listbox.insert(tk.END, f"{name}  ({count} 次)")
        # 保持 normal 状态

    def on_listbox_double_click(self, event):
        """双击列表项，将立绘主体名称填入旧名称输入框"""
        try:
            selection = self.character_listbox.curselection()
            if selection:
                line = self.character_listbox.get(selection[0])
                # 提取主体名称（格式： "主体名称  (次数)"）
                if '(' in line:
                    base_name = line.rsplit('  (', 1)[0].strip()
                    self.old_name_var.set(base_name)
                    self.status_label.config(text=f"已选择: {base_name}", foreground="#569cd6")
        except Exception as e:
            print(f"双击事件出错: {e}")

    def preview_replace(self):
        """预览替换效果：统计将受影响的对话数（基于主体匹配）"""
        old = self.old_name_var.get().strip()
        new = self.new_name_var.get().strip()
        if not old:
            messagebox.showwarning("警告", "请输入旧主体名称")
            return

        old_base = extract_base_name(old)   # 提取用户输入的主体用于比较
        match_case = self.match_case_var.get()
        affected = 0
        examples = []
        # 遍历所有对话，收集受影响的原名称示例
        for script in self.all_data.values():
            if 'c' in script:
                c_val = script['c']
                c_base = extract_base_name(c_val)
                if (match_case and c_base == old_base) or (not match_case and c_base.lower() == old_base.lower()):
                    affected += 1
                    if len(examples) < 3:  # 收集前3个示例
                        examples.append(c_val)

        # 构建预览文本
        new_base = extract_base_name(new)
        preview = f"旧主体: {old_base}\n新主体: {new_base}\n区分大小写: {'是' if match_case else '否'}\n"
        preview += f"将影响 {affected} 条对话\n\n"
        if examples:
            preview += "示例原名称:\n" + "\n".join(examples) + "\n\n"
            preview += "替换后示例:\n"
            for ex in examples:
                _, suffix = split_character_name(ex)
                preview += f"{ex} -> {new_base}{suffix}\n"
        else:
            preview += "无匹配项"

        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.insert('1.0', preview)
        self.preview_text.config(state='disabled')

    def push_history(self):
        """将当前 all_data 的快照压入历史栈"""
        if len(self.history) >= self.history_limit:
            self.history.pop(0)  # 移除最早的记录
        self.history.append(copy.deepcopy(self.all_data))

    def undo(self):
        """撤回上一次替换操作"""
        if not self.history:
            messagebox.showinfo("提示", "没有可撤回的操作")
            return

        # 恢复历史栈顶的数据
        self.all_data = copy.deepcopy(self.history.pop())
        self.modified = True
        self.modified_label.config(text="有未保存的修改")
        self.status_label.config(text="已撤回上一次替换", foreground="#ffcc00")

        # 重新统计立绘列表
        self.rebuild_stats()

    def execute_replace(self):
        """执行批量替换（基于主体匹配，保留后缀）"""
        old = self.old_name_var.get().strip()
        new = self.new_name_var.get().strip()
        if not old:
            messagebox.showwarning("警告", "请输入旧主体名称")
            return

        old_base = extract_base_name(old)
        new_base = extract_base_name(new)  # 只使用新名称的主体部分

        # 再次确认
        if not messagebox.askyesno("确认替换", f"确定要将所有主体为 '{old_base}' 的立绘替换为新主体 '{new_base}'（保留原后缀）吗？\n此操作不可撤销，建议先备份。"):
            return

        match_case = self.match_case_var.get()

        # 记录历史（在执行修改前）
        self.push_history()

        replaced_count = 0
        # 遍历所有对话
        for script in self.all_data.values():
            if 'c' in script:
                c_val = script['c']
                c_base = extract_base_name(c_val)
                if (match_case and c_base == old_base) or (not match_case and c_base.lower() == old_base.lower()):
                    # 保留原后缀
                    _, suffix = split_character_name(c_val)
                    script['c'] = new_base + suffix
                    replaced_count += 1

        if replaced_count > 0:
            self.modified = True
            self.modified_label.config(text="有未保存的修改")
            self.status_label.config(text=f"已替换 {replaced_count} 处，请记得保存", foreground="#ffcc00")
            # 重新统计立绘列表
            self.rebuild_stats()
        else:
            messagebox.showinfo("提示", "没有找到匹配的立绘名称")
            # 没有实际修改，弹出历史记录
            self.history.pop()

    def rebuild_stats(self):
        """重新统计立绘主体出现次数"""
        new_counter = Counter()
        for script in self.all_data.values():
            if 'c' in script and script['c']:
                base = extract_base_name(script['c'])
                new_counter[base] += 1
        self.character_stats = new_counter
        self.filter_list()  # 刷新列表显示

    def save_all(self):
        """保存所有修改到原文件（按块拆分）"""
        if not self.modified:
            messagebox.showinfo("提示", "没有需要保存的修改")
            return

        if not self.script_files:
            messagebox.showerror("错误", "脚本文件列表为空")
            return

        try:
            saved_count = 0
            for file_path in self.script_files:
                # 从文件名猜测ID范围（假设格式 scriptDataN.txt）
                base = os.path.basename(file_path)
                match = re.search(r'(\d+)', base)
                if not match:
                    continue
                chunk_num = int(match.group(1))
                start_id = (chunk_num - 1) * 500 + 1
                end_id = chunk_num * 500

                # 收集该范围内的对话
                chunk_data = {}
                for i in range(start_id, end_id + 1):
                    key = str(i)
                    if key in self.all_data:
                        chunk_data[key] = self.all_data[key]

                # 写入文件（直接覆盖）
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(chunk_data, f, ensure_ascii=False, indent=2)
                saved_count += 1

            self.modified = False
            self.modified_label.config(text="")
            # 保存成功后清空历史，避免撤回保存前的状态
            self.history.clear()
            self.status_label.config(text=f"已保存 {saved_count} 个文件", foreground="#6a9955")
            messagebox.showinfo("保存成功", f"所有修改已保存到 {saved_count} 个文件中")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存时发生错误: {str(e)}")
            self.status_label.config(text="保存失败", foreground="#ff6666")

def main():
    root = tk.Tk()
    app = CharacterBatchRenameTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()