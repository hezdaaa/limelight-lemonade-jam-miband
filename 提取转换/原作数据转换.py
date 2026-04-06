import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import re
import json
import os
import threading
from queue import Queue
import gc

class GalgameScriptConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Galgame剧本格式转换器 - 最终整合版")
        self.root.geometry("1000x750")
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="就绪")
        self.is_processing = False
        self.cancel_processing = False
        self.queue = Queue()
        
        self.setup_ui()
        self.check_queue()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        id_label = ttk.Label(control_frame, text="ID起始数字（固定为1）:")
        id_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.id_start_var = tk.StringVar(value="1")
        id_entry = ttk.Entry(control_frame, textvariable=self.id_start_var, width=10, state="readonly")
        id_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        
        convert_button = ttk.Button(control_frame, text="转换", command=self.start_conversion)
        convert_button.grid(row=0, column=2, padx=(0, 10))
        
        self.cancel_button = ttk.Button(control_frame, text="取消", command=self.cancel_processing_func, state=tk.DISABLED)
        self.cancel_button.grid(row=0, column=3, padx=(0, 10))
        
        import_button = ttk.Button(control_frame, text="导入JSON文件", command=self.import_json_files)
        import_button.grid(row=0, column=4, padx=(0, 10))
        
        export_button = ttk.Button(control_frame, text="导出为TXT文件", command=self.export_txt)
        export_button.grid(row=0, column=5, padx=(0, 10))
        
        clear_button = ttk.Button(control_frame, text="清除", command=self.clear_all)
        clear_button.grid(row=0, column=6, padx=(0, 10))
        
        example_button = ttk.Button(control_frame, text="加载示例", command=self.load_example)
        example_button.grid(row=0, column=7)
        
        self.file_info_var = tk.StringVar(value="未选择文件")
        file_info_label = ttk.Label(control_frame, textvariable=self.file_info_var, foreground="blue")
        file_info_label.grid(row=0, column=8, padx=(20, 0))
        
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_text)
        self.progress_label.grid(row=0, column=0, sticky=tk.W)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        input_label = ttk.Label(main_frame, text="原始剧本格式:")
        input_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        output_label = ttk.Label(main_frame, text="转换后格式 (JSON):")
        output_label.grid(row=2, column=1, sticky=tk.W, pady=(0, 5))
        
        self.input_text = scrolledtext.ScrolledText(main_frame, height=25, width=50, wrap=tk.WORD)
        self.input_text.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        self.output_text = scrolledtext.ScrolledText(main_frame, height=25, width=50, wrap=tk.WORD)
        self.output_text.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.imported_files = []
        self.bind_mouse_wheel()
    
    def check_queue(self):
        try:
            while not self.queue.empty():
                message_type, data = self.queue.get_nowait()
                if message_type == "progress_update":
                    self.progress_var.set(data["progress"])
                    self.progress_text.set(data["message"])
                elif message_type == "status_update":
                    self.status_var.set(data)
                elif message_type == "file_info":
                    self.file_info_var.set(data)
                elif message_type == "output_text":
                    self.output_text.delete("1.0", tk.END)
                    self.output_text.insert("1.0", data)
                elif message_type == "input_text":
                    self.input_text.delete("1.0", tk.END)
                    self.input_text.insert("1.0", data)
                elif message_type == "processing_done":
                    self.is_processing = False
                    self.cancel_processing = False
                    self.cancel_button.config(state=tk.DISABLED)
                    self.progress_text.set("处理完成")
                elif message_type == "processing_error":
                    self.is_processing = False
                    self.cancel_processing = False
                    self.cancel_button.config(state=tk.DISABLED)
                    self.progress_text.set("处理出错")
                    messagebox.showerror("错误", data)
        except Exception as e:
            print(f"队列处理错误: {e}")
        self.root.after(100, self.check_queue)
    
    def start_conversion(self):
        if self.is_processing:
            return
        self.is_processing = True
        self.cancel_processing = False
        self.cancel_button.config(state=tk.NORMAL)
        thread = threading.Thread(target=self.convert_script_thread)
        thread.daemon = True
        thread.start()
    
    def cancel_processing_func(self):
        if self.is_processing:
            self.cancel_processing = True
            self.status_var.set("正在取消处理...")
    
    def bind_mouse_wheel(self):
        def on_mouse_wheel(event, text_widget):
            text_widget.yview_scroll(int(-1*(event.delta/120)), "units")
        self.input_text.bind("<MouseWheel>", lambda e: on_mouse_wheel(e, self.input_text))
        self.output_text.bind("<MouseWheel>", lambda e: on_mouse_wheel(e, self.output_text))
        self.input_text.bind("<Button-4>", lambda e: self.input_text.yview_scroll(-1, "units"))
        self.input_text.bind("<Button-5>", lambda e: self.input_text.yview_scroll(1, "units"))
        self.output_text.bind("<Button-4>", lambda e: self.output_text.yview_scroll(-1, "units"))
        self.output_text.bind("<Button-5>", lambda e: self.output_text.yview_scroll(1, "units"))
    
    def import_json_files(self):
        if self.is_processing:
            messagebox.showwarning("警告", "正在处理中，请稍后再试")
            return
        filetypes = [("JSON文件", "*.json"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        files = filedialog.askopenfilenames(title="选择JSON文件", filetypes=filetypes)
        if not files:
            return
        self.is_processing = True
        self.cancel_processing = False
        self.cancel_button.config(state=tk.NORMAL)
        thread = threading.Thread(target=self.process_files_import, args=(files,))
        thread.daemon = True
        thread.start()
    
    def process_files_import(self, files):
        try:
            self.queue.put(("status_update", f"正在处理 {len(files)} 个文件..."))
            self.queue.put(("progress_update", {"progress": 0, "message": "开始导入文件..."}))
            self.imported_files = list(files)
            total_files = len(files)
            max_display_files = 10
            display_files = min(total_files, max_display_files)
            self.queue.put(("input_text", ""))
            all_content = ""
            for i, file_path in enumerate(self.imported_files[:display_files]):
                if self.cancel_processing:
                    break
                try:
                    progress = (i + 1) / display_files * 100
                    self.queue.put(("progress_update", {"progress": progress, "message": f"正在读取文件: {os.path.basename(file_path)} ({i+1}/{display_files})"}))
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        content = f.read()
                        all_content += f"\n{'='*60}\n文件: {os.path.basename(file_path)}\n{'='*60}\n" + content
                        if i < display_files - 1:
                            all_content += "\n\n"
                    gc.collect()
                except Exception as e:
                    self.queue.put(("status_update", f"无法读取文件: {file_path}\n错误: {str(e)}"))
            if not self.cancel_processing:
                if total_files > display_files:
                    all_content += f"\n\n{'='*60}\n提示: 还有 {total_files - display_files} 个文件未显示（共 {total_files} 个文件）\n{'='*60}"
                self.queue.put(("input_text", all_content))
                if total_files == 1:
                    self.queue.put(("file_info", f"已导入: {os.path.basename(self.imported_files[0])}"))
                else:
                    self.queue.put(("file_info", f"已导入 {total_files} 个文件"))
                self.queue.put(("status_update", f"已成功导入 {total_files} 个文件"))
        except Exception as e:
            self.queue.put(("processing_error", f"导入文件时出错: {str(e)}"))
        finally:
            self.queue.put(("processing_done", None))
    
    def export_txt(self):
        output_text = self.output_text.get("1.0", tk.END).strip()
        if not output_text or output_text == "请输入原始剧本数据" or output_text.startswith("转换错误"):
            messagebox.showwarning("警告", "没有可导出的内容，请先进行转换")
            return
        
        save_dir = filedialog.askdirectory(title="选择保存目录")
        if not save_dir:
            return
        
        try:
            json_data = json.loads(output_text)
            if not isinstance(json_data, dict):
                messagebox.showerror("错误", "输出内容不是有效的JSON对象")
                return
            
            items = sorted(json_data.items(), key=lambda x: int(x[0]))
            total = len(items)
            if total == 0:
                messagebox.showwarning("警告", "没有有效的对话条目")
                return
            
            chunk_size = 500
            num_chunks = (total + chunk_size - 1) // chunk_size
            
            for chunk_idx in range(num_chunks):
                start = chunk_idx * chunk_size
                end = min(start + chunk_size, total)
                chunk_items = items[start:end]
                chunk_dict = {k: v for k, v in chunk_items}
                filename = f"scriptData{chunk_idx+1}.txt"
                filepath = os.path.join(save_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(chunk_dict, f, ensure_ascii=False, indent=2)
                self.status_var.set(f"已保存: {filename} ({len(chunk_items)}条)")
            
            messagebox.showinfo("完成", f"已成功导出 {num_chunks} 个文件到:\n{save_dir}")
            self.status_var.set(f"导出完成，共 {num_chunks} 个文件")
            
        except json.JSONDecodeError as e:
            error_msg = f"输出内容不是有效的JSON:\n{str(e)}\n\n是否仍将当前内容作为纯文本导出？"
            if messagebox.askyesno("JSON格式错误", error_msg):
                filename = "scriptData_error.txt"
                filepath = os.path.join(save_dir, filename)
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(output_text)
                    messagebox.showinfo("完成", f"已作为纯文本导出到:\n{filepath}")
                except Exception as e2:
                    messagebox.showerror("错误", f"保存纯文本失败: {str(e2)}")
        except Exception as e:
            messagebox.showerror("错误", f"导出时出错: {str(e)}")
    
    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self.imported_files = []
        self.file_info_var.set("未选择文件")
        self.status_var.set("已清除所有内容")
        self.progress_var.set(0)
        self.progress_text.set("就绪")
    
    def clean_text(self, text):
        if not text:
            return ""
        text = text.replace("\\n", "\n")
        text = text.replace(";", "")
        special_chars = ["%n", "；", "\\t", "\\r"]
        for char in special_chars:
            text = text.replace(char, "")
        return text.strip()
        
    def format_speaker(self, speaker):
        if not speaker:
            return ""
        if "【" not in speaker and "】" not in speaker:
            return f"【{speaker}】"
        return speaker
    
    # ---------- 立绘与背景提取 ----------
    def extract_background_and_blur_from_entry(self, entry):
        if len(entry) < 5:
            return "", False
        scene_data = entry[4]
        if not isinstance(scene_data, dict):
            return "", False
        data_array = scene_data.get("data")
        if not isinstance(data_array, list):
            return "", False
        for item in data_array:
            if not isinstance(item, list) or len(item) < 3:
                continue
            obj_type = item[1]
            params = item[2]
            if obj_type == "stage" and isinstance(params, dict):
                redraw = params.get("redraw")
                if redraw and isinstance(redraw, dict):
                    imageFile = redraw.get("imageFile")
                    if imageFile and isinstance(imageFile, dict):
                        file = imageFile.get("file", "")
                        # 确保 file 是字符串
                        if not isinstance(file, str):
                            file = str(file) if file is not None else ""
                        if file:
                            if '.' in file:
                                file = file.rsplit('.', 1)[0]
                            has_blur = self.check_doBoxBlur(imageFile)
                            return file, has_blur
        return "", False
    
    def check_doBoxBlur(self, obj):
        if isinstance(obj, dict):
            for v in obj.values():
                if self.check_doBoxBlur(v):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if self.check_doBoxBlur(item):
                    return True
        elif isinstance(obj, str) and "doBoxBlur" in obj:
            return True
        return False
    
    def extract_characters_from_entry(self, entry):
        if len(entry) < 5:
            return ""
        scene_data = entry[4]
        if not isinstance(scene_data, dict):
            return ""
        data_array = scene_data.get("data")
        if not isinstance(data_array, list):
            return ""
        return self.extract_characters(data_array)
    
    def extract_characters(self, data_array):
        if not data_array or not isinstance(data_array, list):
            return ""
        chars = []
        for item in data_array:
            if not isinstance(item, list) or len(item) < 3:
                continue
            obj_type = item[1]
            params = item[2]
            if obj_type == "character" and params.get("showmode") == 3:
                redraw = params.get("redraw")
                if redraw and isinstance(redraw, dict):
                    imageFile = redraw.get("imageFile")
                    if imageFile and isinstance(imageFile, dict):
                        file = imageFile.get("file", "")
                        # 确保 file 是字符串
                        if not isinstance(file, str):
                            file = str(file) if file is not None else ""
                        if file:
                            options = imageFile.get("options", {})
                            parts = []
                            dress = options.get("dress", "")
                            pose = options.get("pose", "")
                            if dress:
                                parts.append(f"dress={dress}")
                            if pose:
                                parts.append(f"pose={pose}")
                            query = "&".join(parts)
                            char_str = f"{file}?{query}" if query else file
                            chars.append(char_str)
        return ";".join(chars)
    
    def extract_text_from_entry(self, entry):
        try:
            if len(entry) >= 2 and isinstance(entry[1], list) and len(entry[1]) > 0:
                inner = entry[1][0]
                if isinstance(inner, list) and len(inner) >= 2:
                    raw_text = inner[1]
                    if isinstance(raw_text, str):
                        return self.clean_text(raw_text)
        except Exception:
            pass
        return ""
    
    def extract_speaker_from_entry(self, entry):
        try:
            if len(entry) >= 2 and isinstance(entry[1], list) and len(entry[1]) > 0:
                inner = entry[1][0]
                if isinstance(inner, list) and len(inner) >= 1:
                    inner_speaker = inner[0]
                    if isinstance(inner_speaker, str) and inner_speaker.strip():
                        return inner_speaker
            if len(entry) >= 1:
                outer_speaker = entry[0]
                if isinstance(outer_speaker, str) and outer_speaker.strip():
                    return outer_speaker
        except Exception:
            pass
        return ""

    # ---------- 提取 sd/ev 作为 cg ----------
    def extract_cg_from_entry(self, entry):
        """从剧本条目中提取 cg（sd/ev 图层）"""
        if len(entry) < 5:
            return ""
        scene_data = entry[4]
        if not isinstance(scene_data, dict):
            return ""
        data_array = scene_data.get("data")
        if not isinstance(data_array, list):
            return ""
        
        cg_list = []
        for item in data_array:
            if not isinstance(item, list) or len(item) < 3:
                continue
            obj_type = item[1]          # "sdlayer" 或 "event"
            params = item[2]
            if obj_type in ("sdlayer", "event") and isinstance(params, dict):
                redraw = params.get("redraw")
                if redraw and isinstance(redraw, dict):
                    imageFile = redraw.get("imageFile")
                    if imageFile and isinstance(imageFile, dict):
                        file = imageFile.get("file", "")
                        # 确保 file 是字符串
                        if not isinstance(file, str):
                            file = str(file) if file is not None else ""
                        if file:
                            # 去除扩展名
                            if '.' in file:
                                file = file.rsplit('.', 1)[0]
                            cg_list.append(file)
        return ";".join(cg_list)
    # --------------------------------------
    
    # ---------- 立绘处理核心 ----------
    def process_characters(self, entries):
        def get_raw_speaker(speaker_formatted):
            if not speaker_formatted:
                return ""
            match = re.search(r'【(.+?)】', speaker_formatted)
            if match:
                return match.group(1)
            return speaker_formatted.strip()
        
        def unique_poses(poses_str):
            if not poses_str:
                return poses_str
            items = poses_str.split(';')
            seen = set()
            unique = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    unique.append(item)
            return ';'.join(unique)
        
        is_ref = [False] * len(entries)
        
        for i, item in enumerate(entries):
            speaker_formatted = item.get("speaker", "")
            if not speaker_formatted:
                continue
            char_str = item.get("characters", "")
            if not char_str:
                continue
            poses = char_str.split(';')
            original_len = len(poses)
            poses = [p for idx, p in enumerate(poses) if p not in poses[:idx]]
            speaker_raw = get_raw_speaker(speaker_formatted)
            matched = [p for p in poses if p.startswith(speaker_raw + '.')]
            if matched:
                item["characters"] = matched[0]
                if original_len > 1:
                    is_ref[i] = True
            else:
                item["characters"] = ';'.join(poses)
        
        for i, item in enumerate(entries):
            if is_ref[i]:
                continue
            char_str = item.get("characters", "")
            if not char_str:
                continue
            poses = char_str.split(';')
            poses = [p for idx, p in enumerate(poses) if p not in poses[:idx]]
            if len(poses) <= 1:
                item["characters"] = ';'.join(poses)
                continue
            speaker_formatted = item.get("speaker", "")
            speaker_raw = get_raw_speaker(speaker_formatted)
            ref_idx = None
            for j in range(i-1, -1, -1):
                if is_ref[j]:
                    ref_idx = j
                    break
            if ref_idx is not None:
                ref_speaker_formatted = entries[ref_idx].get("speaker", "")
                ref_raw = get_raw_speaker(ref_speaker_formatted)
                matched = [p for p in poses if p.startswith(ref_raw + '.')]
                if matched:
                    item["characters"] = matched[0]
                else:
                    item["characters"] = poses[0]
            else:
                item["characters"] = poses[0]
        
        for item in entries:
            if "characters" in item and item["characters"]:
                item["characters"] = unique_poses(item["characters"])
    
    # ---------- 顺序查找所有剧本条目，包括nexts跳转和chapter标记 ----------
    def find_all_script_entries_ordered(self, input_data):
        # 去除开头的 UTF-8 BOM
        if input_data.startswith('\ufeff'):
            input_data = input_data[1:]
        
        chapter_pattern = re.compile(r'chapter.*?(\d+-\d+)', re.IGNORECASE)
        chapter_matches = []
        for match in chapter_pattern.finditer(input_data):
            chapter_str = match.group(1)
            pos = match.start()
            chapter_matches.append((pos, chapter_str))
        
        seen = set()
        unique_chapters = []
        for pos, cs in chapter_matches:
            if cs not in seen:
                seen.add(cs)
                unique_chapters.append((pos, cs))
        unique_chapters.sort(key=lambda x: x[0])
        
        dialogue_patterns = [
            (r'(\[null,\s*\[\[null,\s*"([^"]*)"[^\]]*\]\][^\]]*\])', "no_speaker"),
            (r'(\["([^"]*)",\s*\[\["([^"]*)",\s*"([^"]*)"[^\]]*\]\][^\]]*\])', "inner_speaker"),
            (r'(\["([^"]*)",\s*\[\[null,\s*"([^"]*)"[^\]]*\]\][^\]]*\])', "outer_speaker"),
            (r'(\["([^"]*)",\s*\[\[null,\s*"([^"]*)",\d+,"[^"]*","[^"]*"\]\][^\]]*\])', "outer_speaker"),
            (r'(\[null,\s*\[\[null,\s*"([^"]*)",\d+,"[^"]*","[^"]*"\]\][^\]]*\])', "no_speaker")
        ]
        
        current_pos = 0
        length = len(input_data)
        all_items = []
        
        while current_pos < length:
            if self.cancel_processing:
                break
            
            earliest_match = None
            earliest_pattern_index = -1
            earliest_pos = length
            
            for i, (pattern, _) in enumerate(dialogue_patterns):
                match = re.search(pattern, input_data[current_pos:])
                if match:
                    match_pos = current_pos + match.start()
                    if match_pos < earliest_pos:
                        earliest_pos = match_pos
                        earliest_match = match
                        earliest_pattern_index = i
            
            if earliest_match is None:
                break
            
            start_pos = earliest_pos
            pos = start_pos
            stack = 0
            in_string = False
            escape = False
            end_pos = -1
            
            while pos < length:
                ch = input_data[pos]
                if not in_string:
                    if ch == '[':
                        stack += 1
                    elif ch == ']':
                        stack -= 1
                        if stack == 0:
                            end_pos = pos + 1
                            break
                    elif ch == '"':
                        in_string = True
                else:
                    if ch == '"' and not escape:
                        in_string = False
                    elif ch == '\\' and not escape:
                        escape = True
                    else:
                        escape = False
                pos += 1
            
            if end_pos == -1:
                current_pos = start_pos + 1
                continue
            
            entry_str = input_data[start_pos:end_pos]
            
            try:
                entry = json.loads(entry_str)
                if isinstance(entry, list) and len(entry) >= 2:
                    text = self.extract_text_from_entry(entry)
                    if text:
                        speaker_raw = self.extract_speaker_from_entry(entry)
                        bg, blur = self.extract_background_and_blur_from_entry(entry)
                        characters = self.extract_characters_from_entry(entry)
                        cg = self.extract_cg_from_entry(entry)
                        entry_dict = {
                            "speaker_raw": speaker_raw,
                            "speaker": self.format_speaker(speaker_raw),
                            "text": text,
                            "background": bg,
                            "blur": blur,
                            "characters": characters,
                            "cg": cg
                        }
                        all_items.append((start_pos, entry_dict, True))
                    
                    if len(entry) >= 5 and isinstance(entry[4], dict):
                        scene_dict = entry[4]
                        nexts = scene_dict.get("nexts")
                        if isinstance(nexts, list):
                            for next_item in nexts:
                                if isinstance(next_item, dict) and "target" in next_item:
                                    target = next_item["target"]
                                    entry_dict_next = {
                                        "speaker_raw": f"[{target}]",
                                        "speaker": f"[{target}]",
                                        "text": "",
                                        "background": "ecall",
                                        "blur": False,
                                        "characters": "",
                                        "cg": ""
                                    }
                                    all_items.append((end_pos, entry_dict_next, False))
            except json.JSONDecodeError:
                pattern_type = dialogue_patterns[earliest_pattern_index][1]
                if pattern_type == "no_speaker":
                    text = earliest_match.group(2)
                elif pattern_type == "inner_speaker":
                    text = earliest_match.group(4)
                else:
                    text = earliest_match.group(3)
                text = self.clean_text(text)
                if text:
                    entry_dict = {
                        "speaker_raw": "",
                        "speaker": "",
                        "text": text,
                        "background": "",
                        "blur": False,
                        "characters": "",
                        "cg": ""
                    }
                    all_items.append((start_pos, entry_dict, True))
            
            current_pos = end_pos
        
        all_items.sort(key=lambda x: x[0])
        
        final_entries = []
        chap_idx = 0
        total_chapters = len(unique_chapters)
        
        for pos, item, _ in all_items:
            while chap_idx < total_chapters and unique_chapters[chap_idx][0] < pos:
                _, cs = unique_chapters[chap_idx]
                final_entries.append({
                    "speaker_raw": f"[CHAPTER{cs}]",
                    "speaker": f"[CHAPTER{cs}]",
                    "text": "",
                    "background": "ecall",
                    "blur": False,
                    "characters": "",
                    "cg": ""
                })
                chap_idx += 1
            final_entries.append(item)
        
        while chap_idx < total_chapters:
            _, cs = unique_chapters[chap_idx]
            final_entries.append({
                "speaker_raw": f"[CHAPTER{cs}]",
                "speaker": f"[CHAPTER{cs}]",
                "text": "",
                "background": "ecall",
                "blur": False,
                "characters": "",
                "cg": ""
            })
            chap_idx += 1
        
        return final_entries
    
    # ---------- 转换线程 ----------
    def convert_script_thread(self):
        try:
            if self.imported_files:
                self.queue.put(("progress_update", {"progress": 0, "message": "正在从文件读取内容..."}))
                all_entries = []
                total_files = len(self.imported_files)
                for i, file_path in enumerate(self.imported_files):
                    if self.cancel_processing:
                        break
                    progress = (i + 1) / total_files * 50
                    self.queue.put(("progress_update", {"progress": progress, "message": f"正在处理文件: {os.path.basename(file_path)} ({i+1}/{total_files})"}))
                    try:
                        with open(file_path, 'r', encoding='utf-8-sig') as f:
                            content = f.read()
                        file_entries = self.find_all_script_entries_ordered(content)
                        all_entries.extend(file_entries)
                        self.queue.put(("status_update", f"文件 {os.path.basename(file_path)} 提取了 {len(file_entries)} 条对话"))
                        gc.collect()
                    except Exception as e:
                        self.queue.put(("status_update", f"读取文件 {os.path.basename(file_path)} 出错: {str(e)}"))
                if self.cancel_processing:
                    return
                entries = all_entries
                self.queue.put(("status_update", f"总共成功提取 {len(entries)} 条对话"))
            else:
                input_data = self.input_text.get("1.0", tk.END).strip()
                if not input_data:
                    self.queue.put(("output_text", "请输入原始剧本数据"))
                    self.queue.put(("status_update", "错误: 请输入原始剧本数据"))
                    self.queue.put(("processing_done", None))
                    return
                entries = self.find_all_script_entries_ordered(input_data)
                self.queue.put(("status_update", f"成功提取 {len(entries)} 条对话"))
            
            if self.cancel_processing:
                return
            
            if not entries:
                self.queue.put(("status_update", "警告: 未找到匹配的剧本条目"))
            else:
                self.process_characters(entries)
            
            self.queue.put(("progress_update", {"progress": 75, "message": "正在格式化输出..."}))
            
            result_dict = {}
            id_start = 1
            total_entries = len(entries)
            
            for i, item in enumerate(entries):
                if self.cancel_processing:
                    break
                progress = 75 + (i + 1) / total_entries * 25
                self.queue.put(("progress_update", {"progress": progress, "message": f"正在格式化条目: {i+1}/{total_entries}"}))
                
                current_id = id_start + i
                entry_dict = {}
                if item.get("background"):
                    entry_dict["b"] = item["background"]
                if item.get("speaker"):
                    entry_dict["s"] = item["speaker"]
                if item.get("text"):
                    entry_dict["t"] = item["text"]
                if item.get("characters"):
                    entry_dict["c"] = item["characters"]
                if item.get("blur"):
                    entry_dict["z"] = 2
                if item.get("cg"):
                    entry_dict["cg"] = item["cg"]
                
                if entry_dict:
                    result_dict[str(current_id)] = entry_dict
            
            output_str = json.dumps(result_dict, ensure_ascii=False, indent=2)
            
            if not self.cancel_processing:
                self.queue.put(("output_text", output_str))
                self.queue.put(("processing_done", None))
            
        except Exception as e:
            self.queue.put(("processing_error", f"转换错误: {str(e)}"))
    
    def load_example(self):
        example_data = '''["莉々子",[["莉莉子","「我懂……！　那种地方就应该用奥赛罗棋的方式！\\n连休和周末重叠感觉就像亏了一样—」",42,"「我懂……！　那种地方就应该用奥赛罗棋的方式！连休和周末重叠感觉就像亏了一样—」","「我懂……！　那种地方就应该用奥赛罗棋的方式！连休和周末重叠感觉就像亏了一样—」"]],[{
              "name": "莉々子",
              "pan": 0,
              "type": 0,
              "voice": "rir_009_0001"
            }],1232,{
            "_meswinchange": "MSGWIN",
            "data": [["bgm","bgm",{
                  "name": "bgm",
                  "replay": {
                    "filename": "bgm01",
                    "loop": 1,
                    "start": null,
                    "state": 1,
                    "volume": 100.0
                  },
                  "update": {
                    "state": 1
                  }
                }],["lse","loopse",{
                  "action": [["fade",50]],
                  "name": "lse",
                  "replay": {
                    "filename": "■朝チュン",
                    "loop": 1,
                    "start": null,
                    "state": 0,
                    "volume": 100.0
                  },
                  "update": {
                    "state": 0
                  }
                }],["se","se",{
                  "name": "se"
                }],["stage","stage",{
                  "action": [["zpos",233.33333333333337],["zoomy",200],["ypos",-350],["zoomx",200]],
                  "class": "stage",
                  "name": "stage",
                  "redraw": {
                    "disp": 2,
                    "imageFile": {
                      "file": "居酒屋_店内",
                      "redraw": [["doBoxBlur",2,2],["doBoxBlur",2,2]]
                    },
                    "posName": null
                  },
                  "showmode": 3,
                  "type": null
                }],["莉々子","character",{
                  "action": [["leveloffset","#0,0,0,-50,0,-100,0,-140,0,-190,0,-215,0,-300,0,-450,0,-600"],["zpos",33.333333333333343]],
                  "class": "character",
                  "name": "莉々子",
                  "redraw": {
                    "disp": 2,
                    "imageFile": {
                      "file": "莉々子.stand",
                      "options": {
                        "dress": "制服",
                        "face": "43",
                        "pose": "1"
                      }
                    },
                    "posName": "出"
                  },
                  "showmode": 3,
                  "type": null
                }],["face","msgwin",{
                  "action": [["originy",320],["leveloffset","#0,0,0,-50,0,-100,0,-140,0,-190,0,-215,0,-300,0,-450,0,-600"],["xpos",-280.0],["zoomy",45],["ypos",-140.0],["zoomx",45],["originx",-480]],
                  "class": "msgwin",
                  "name": "face",
                  "redraw": {
                    "disp": 2,
                    "imageFile": {
                      "file": "莉々子.stand",
                      "options": {
                        "dress": "制服",
                        "face": "43",
                        "pose": "1"
                      }
                    },
                    "posName": null
                  },
                  "showmode": 3,
                  "type": null
                }]],
            "env": {
              "name": "env"
            },
            "phonechat_showing": 0,
            "scnchart": "s010*part_010",
            "showdate": {
              "back": null,
              "date": "2-1",
              "fore": null,
              "nowShow": 1
            }
          }],["雪鹰",[[null,"这是一个没有对应立绘的对话",15]],null,1728,{
            "_meswinchange": "MSGWIN"
          }]'''
        
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", example_data)
        self.imported_files = ["示例数据"]
        self.file_info_var.set("示例数据")
        self.status_var.set("已加载示例数据")

def main():
    root = tk.Tk()
    app = GalgameScriptConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()