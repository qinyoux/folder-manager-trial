# 哈利 / Windows 文件夹管理系统原型
import json
import os
import re
import difflib
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk

APP_NAME = "Windows 文件夹管理系统原型"
APP_VERSION = "v0.4.3"
DEFAULT_IGNORE = ".git,node_modules,__pycache__,.idea,.vscode,dist,build"
APP_CONFIG_FILENAME = ".folder-manager.json"
APP_STATE_FILENAME = ".folder-manager.state.json"
TEMPLATES = {
    "通用模板": """# 哈利 / File_list 通用模板
# 规则：
# - 以缩进表示层级，建议每层 2 个空格
# - 目录以 / 结尾
# - 文件直接写文件名
# - 行内可用 # 写说明，程序会忽略其后的注释

ProjectRoot/ # 项目根目录
  README.md # 项目总说明
  docs/ # 文档资料
    README.md # 文档说明
  src/ # 源代码
    README.md # 代码说明
  assets/ # 图片和素材
  logs/ # 比对日志
  snapshots/ # 结构快照
""",
    "DHF模板": """# 哈利 / File_list DHF 模板
DHF_Project/ # DHF 项目根目录
  README.md # 项目总览
  01_需求输入/ # 用户需求、产品需求、法规输入
    README.md # 本目录说明
  02_设计开发/ # 方案设计、开发记录
    README.md
  03_测试验证/ # 测试计划、测试报告
    README.md
  04_发布归档/ # 发布资料、版本归档
    README.md
  logs/
  snapshots/
""",
    "硬件模板": """# 哈利 / File_list 硬件项目模板
Hardware_Project/ # 硬件项目根目录
  README.md # 项目总览
  docs/ # 项目文档
    README.md
  schematic/ # 原理图
  pcb/ # PCB 设计文件
  bom/ # 物料清单
  firmware/ # 固件代码
    README.md
  test/ # 测试记录
  assets/ # 图片、外壳、素材
  logs/
  snapshots/
""",
    "结构模板": """# 哈利 / File_list 结构设计模板
Structure_Project/ # 结构设计项目根目录
  README.md # 项目总说明
  brief/ # 需求简报
  concept/ # 概念方案
  cad/ # 结构设计文件
  render/ # 效果图
  sample/ # 打样资料
  review/ # 评审记录
  logs/
  snapshots/
""",
}
DEFAULT_TEMPLATE = TEMPLATES["通用模板"]
HELP_TEXT = """哈利 / 使用帮助（精简版）

一、这个工具能做什么
- 用 `File_list.md` 定义标准目录
- 一键生成目录 / 空文件
- 扫描真实目录并和标准结构做对比
- 搜索、打开、定位、复制文件路径
- 对两个文件或两个文件夹做左右对比
- 用 AI 生成差异总结

二、第一次使用，推荐顺序
1. 选择目标文件夹
2. 选择模板并点击“加载模板”
3. 按需要修改 `File_list.md`
4. 点击“初始化模板”
5. 点击“生成结构”
6. 点击“扫描结构”
7. 点击“文件/文件夹对比”或“对比差异”查看结果
8. 需要补齐时再点“一键补齐缺失项”

三、`File_list.md` 怎么写
- 每层缩进 2 个空格
- 目录以 `/` 结尾
- 文件不要加 `/`
- 行尾可加 `# 注释`

示例：
ProjectRoot/
  README.md
  docs/
    spec.md
  src/
    main.py

四、对比窗口怎么看
1. 左边 = OLD / 基准 / 被对照内容
2. 右边 = NEW / 当前 / 对比结果
3. 文件对比时：
   - 左侧看旧版本原文
   - 右侧先看新版本原文，再看 diff
4. 文件夹对比时：
   - 左侧看“仅左侧存在”与“一致文件”
   - 右侧看“仅右侧存在”与“变更文件”

五、diff 颜色说明
- 绿色：新增内容（NEW 里有，OLD 里没有）
- 红色：删除内容（OLD 里有，NEW 里没有）
- 蓝色：文件头 / 路径信息（`---` / `+++`）
- 紫色：变更块定位（`@@ ... @@`）

六、什么时候用哪个功能
- 想建标准目录：初始化模板 / 生成结构
- 想检查目录有没有跑偏：扫描结构 / 对比差异
- 想从老项目反推模板：反向生成模板
- 想看两个文件具体改了什么：文件/文件夹对比
- 想快速给老板汇报：AI 总结差异

七、常见问题
1. 搜索不到文件：先检查目标文件夹、关键词、忽略规则
2. 多余项很多：通常是模板太旧，或真实目录里有临时文件
3. 一键补齐没生效：它只能补模板里已经定义的内容
4. 左右不知道谁是 old / new：记住“左旧右新，左基准右当前”

八、一句话记住
这不是单纯“建文件夹”的工具，而是一个把项目目录标准化、可检查、可对比、可交接的本地工作台。
"""


def normalize_indent(line: str) -> int:
    expanded = line.replace("\t", "  ")
    return len(expanded) - len(expanded.lstrip(" "))


def strip_comment(line: str) -> str:
    if "#" not in line:
        return line.rstrip()
    return line.split("#", 1)[0].rstrip()


def parse_file_list(content: str):
    entries = []
    stack = []

    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = normalize_indent(raw_line)
        level = indent // 2
        body = strip_comment(raw_line).strip()
        if not body:
            continue

        while len(stack) > level:
            stack.pop()

        name = body.rstrip()
        is_dir = name.endswith("/")
        clean_name = name[:-1] if is_dir else name

        relative_parts = stack + [clean_name]
        relative_path = Path(*relative_parts)
        entries.append({
            "path": relative_path,
            "is_dir": is_dir,
            "level": level,
        })

        if is_dir:
            stack = stack[:level]
            stack.append(clean_name)

    return entries


def create_structure(base_dir: Path, entries):
    created = []
    for entry in entries:
        target = base_dir / entry["path"]
        if entry["is_dir"]:
            target.mkdir(parents=True, exist_ok=True)
            created.append(f"[DIR]  {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text("", encoding="utf-8")
                created.append(f"[FILE] {target}")
            else:
                created.append(f"[SKIP] {target}")
    return created


def parse_ignore_list(raw_text: str):
    return {item.strip() for item in raw_text.split(",") if item.strip()}


def build_tree_lines(base_dir: Path, ignore_names=None):
    ignore_names = ignore_names or set()
    lines = [base_dir.name + "/"]

    def walk(current: Path, prefix: str = ""):
        filtered_items = [item for item in current.iterdir() if item.name not in ignore_names]
        items = sorted(filtered_items, key=lambda item: (item.is_file(), item.name.lower()))
        for index, item in enumerate(items):
            connector = "└── " if index == len(items) - 1 else "├── "
            suffix = "/" if item.is_dir() else ""
            lines.append(prefix + connector + item.name + suffix)
            if item.is_dir():
                extension = "    " if index == len(items) - 1 else "│   "
                walk(item, prefix + extension)

    walk(base_dir)
    return lines


def save_snapshot(base_dir: Path, ignore_names=None):
    snapshot_dir = base_dir / "snapshots"
    snapshot_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    snapshot_path = snapshot_dir / f"tree-{timestamp}.md"
    tree_content = "# 哈利 / 当前目录结构\n\n```text\n" + "\n".join(build_tree_lines(base_dir, ignore_names)) + "\n```\n"
    snapshot_path.write_text(tree_content, encoding="utf-8")
    return snapshot_path


def collect_relative_structure(base_dir: Path, ignore_names=None):
    ignore_names = ignore_names or set()
    results = set()
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [directory for directory in dirs if directory not in ignore_names]
        files = [file_name for file_name in files if file_name not in ignore_names]
        root_path = Path(root)
        rel_root = root_path.relative_to(base_dir)
        for directory in dirs:
            rel = (rel_root / directory).as_posix().strip(".")
            if rel:
                results.add(rel + "/")
        for file_name in files:
            rel = (rel_root / file_name).as_posix().strip(".")
            if rel:
                results.add(rel)
    return results


def expected_relative_structure(entries):
    return {entry["path"].as_posix() + ("/" if entry["is_dir"] else "") for entry in entries}


def compare_structure(base_dir: Path, entries, ignore_names=None):
    expected = expected_relative_structure(entries)
    actual = collect_relative_structure(base_dir, ignore_names)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    shared = sorted(expected & actual)

    report = []
    report.append("# 哈利 / 目录结构差异报告")
    report.append(f"- 检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"- 目标目录：{base_dir}")
    report.append(f"- 应有项目数：{len(expected)}")
    report.append(f"- 实际项目数：{len(actual)}")
    report.append("")
    report.append("## 缺失项")
    report.extend([f"- {item}" for item in missing] or ["- 无"])
    report.append("")
    report.append("## 多余项")
    report.extend([f"- {item}" for item in extra] or ["- 无"])
    report.append("")
    report.append("## 已匹配项")
    report.extend([f"- {item}" for item in shared[:200]] or ["- 无"])
    if len(shared) > 200:
        report.append(f"- ... 其余 {len(shared) - 200} 项省略")

    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = logs_dir / f"compare-{timestamp}.log"
    log_path.write_text("\n".join(report), encoding="utf-8")
    return log_path, missing, extra


def generate_template_from_directory(base_dir: Path, ignore_names=None):
    ignore_names = ignore_names or set()
    lines = [f"{base_dir.name}/ # 自动生成的目录模板"]

    def walk(current: Path, level: int):
        filtered_items = [item for item in current.iterdir() if item.name not in ignore_names]
        items = sorted(filtered_items, key=lambda item: (item.is_file(), item.name.lower()))
        for item in items:
            indent = "  " * level
            if item.is_dir():
                lines.append(f"{indent}{item.name}/")
                walk(item, level + 1)
            else:
                lines.append(f"{indent}{item.name}")

    walk(base_dir, 1)
    return "\n".join(lines) + "\n"


TEXT_COMPARE_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".html", ".htm", ".js", ".ts", ".css", ".yaml", ".yml", ".ini", ".log", ".xml", ".sql"}


def is_text_like_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_COMPARE_EXTENSIONS


def safe_read_text(path: Path, max_chars: int = 200000):
    data = path.read_text(encoding="utf-8", errors="ignore")
    return data[:max_chars]


def compare_two_files(left_path: Path, right_path: Path):
    left_exists = left_path.exists()
    right_exists = right_path.exists()
    if not left_exists or not right_exists:
        return {
            "mode": "file",
            "status": "missing",
            "left_exists": left_exists,
            "right_exists": right_exists,
            "summary": "文件不存在，无法完成对比",
            "diff_text": "",
            "changed_files": [],
        }

    left_text = safe_read_text(left_path)
    right_text = safe_read_text(right_path)
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()
    diff_lines = list(difflib.unified_diff(left_lines, right_lines, fromfile=str(left_path), tofile=str(right_path), lineterm=""))
    status = "same" if not diff_lines else "changed"
    summary = "文件内容一致" if status == "same" else f"发现 {len(diff_lines)} 行差异输出（以内容 diff 为准）"
    if not is_text_like_file(left_path) or not is_text_like_file(right_path):
        summary += "；当前格式不在常用文本白名单内，已尽力按文本内容读取比较，结果可能受编码影响"
    return {
        "mode": "file",
        "status": status,
        "left_exists": True,
        "right_exists": True,
        "summary": summary,
        "diff_text": "\n".join(diff_lines) if diff_lines else "两份文件内容一致",
        "changed_files": [str(left_path)] if status == "changed" else [],
        "left_excerpt": left_text[:12000],
        "right_excerpt": right_text[:12000],
    }


def compare_two_directories(left_dir: Path, right_dir: Path, ignore_names=None):
    ignore_names = ignore_names or set()
    left_items = collect_relative_structure(left_dir, ignore_names) if left_dir.exists() else set()
    right_items = collect_relative_structure(right_dir, ignore_names) if right_dir.exists() else set()
    left_only = sorted(left_items - right_items)
    right_only = sorted(right_items - left_items)
    common = sorted(left_items & right_items)
    changed_files = []
    same_files = []

    for rel in common:
        if rel.endswith('/'):
            continue
        lp = left_dir / rel
        rp = right_dir / rel
        if not lp.exists() or not rp.exists():
            continue
        if is_text_like_file(lp) and is_text_like_file(rp):
            if safe_read_text(lp, 50000) != safe_read_text(rp, 50000):
                changed_files.append(rel)
            else:
                same_files.append(rel)
        else:
            if lp.stat().st_size != rp.stat().st_size:
                changed_files.append(rel)
            else:
                same_files.append(rel)

    report = []
    report.append('[目录对比结果]')
    report.append(f'左侧目录：{left_dir}')
    report.append(f'右侧目录：{right_dir}')
    report.append(f'仅左侧存在：{len(left_only)} 项')
    report.append(f'仅右侧存在：{len(right_only)} 项')
    report.append(f'内容变更文件：{len(changed_files)} 项')
    report.append(f'完全一致文件：{len(same_files)} 项')
    report.append('')
    report.append('[仅左侧存在]')
    report.extend([f'- {item}' for item in left_only[:200]] or ['- 无'])
    report.append('')
    report.append('[仅右侧存在]')
    report.extend([f'- {item}' for item in right_only[:200]] or ['- 无'])
    report.append('')
    report.append('[内容变更文件]')
    report.extend([f'- {item}' for item in changed_files[:200]] or ['- 无'])
    report.append('')
    report.append('[完全一致文件]')
    report.extend([f'- {item}' for item in same_files[:100]] or ['- 无'])

    return {
        "mode": "directory",
        "status": "compared",
        "left_only": left_only,
        "right_only": right_only,
        "changed_files": changed_files,
        "same_files": same_files,
        "summary": f"左侧独有 {len(left_only)} 项，右侧独有 {len(right_only)} 项，变更文件 {len(changed_files)} 项",
        "diff_text": "\n".join(report),
    }


def build_ai_messages_from_compare(compare_result, mode="老板摘要"):
    mode_prompts = {
        "老板摘要": "请用老板能快速看懂的方式输出：1）这次改了什么 2）最值得注意的变化 3）潜在风险 4）是否建议进一步人工确认。语言简洁，偏结论。",
        "技术摘要": "请用技术视角输出：1）变更概述 2）具体差异点 3）风险点 4）建议复核文件/模块。语言准确，允许较技术化。",
        "简洁摘要": "请用最短结构化方式输出 3-5 条重点结论。",
    }
    lines = [
        '请你作为文件差异分析助手，总结以下对比结果。',
        mode_prompts.get(mode, mode_prompts["老板摘要"]),
        '',
        '【系统摘要】',
        compare_result.get('summary', ''),
        '',
        '【差异详情】',
        compare_result.get('diff_text', '')[:30000],
    ]
    if compare_result.get('mode') == 'file':
        if compare_result.get('left_excerpt'):
            lines.extend(['', '【左侧文件片段】', compare_result.get('left_excerpt', '')[:8000]])
        if compare_result.get('right_excerpt'):
            lines.extend(['', '【右侧文件片段】', compare_result.get('right_excerpt', '')[:8000]])
    return '\n'.join(lines)


def call_openai_compatible_api(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 60):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是专业的文件差异分析助手，输出中文，要求简洁、结构化、可执行。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    url = base_url.rstrip('/') + '/chat/completions'
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('Authorization', f'Bearer {api_key}')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')
    data = json.loads(raw)
    return data['choices'][0]['message']['content']


def open_in_system_explorer(target_path: Path):
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", str(target_path)])
        else:
            subprocess.Popen(["xdg-open", str(target_path)])
        return True
    except Exception:
        return False


def open_with_default_app(target_path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(target_path))
        else:
            subprocess.Popen(["xdg-open", str(target_path)])
        return True
    except Exception:
        return False


def format_file_size(size_bytes: int):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def load_project_config(base_dir: Path):
    config_path = base_dir / APP_CONFIG_FILENAME
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_project_config(base_dir: Path, config: dict):
    config_path = base_dir / APP_CONFIG_FILENAME
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def load_app_state(base_dir: Path):
    state_path = base_dir / APP_STATE_FILENAME
    if not state_path.exists():
        return {"favorites": [], "recent_dirs": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"favorites": [], "recent_dirs": []}


def save_app_state(base_dir: Path, state: dict):
    state_path = base_dir / APP_STATE_FILENAME
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


class FolderManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1420x920")
        self.root.minsize(1180, 760)
        self.root.resizable(True, True)
        self.root.configure(bg="#f3f6fb")
        self.target_dir = tk.StringVar()
        self.template_name = tk.StringVar(value="通用模板")
        self.ignore_names = tk.StringVar(value=DEFAULT_IGNORE)
        self.search_keyword = tk.StringVar()
        self.project_note = tk.StringVar()
        self.ai_base_url = tk.StringVar(value="https://api.deepseek.com/v1")
        self.ai_api_key = tk.StringVar()
        self.ai_model = tk.StringVar(value="deepseek-chat")
        self.ai_summary_mode = tk.StringVar(value="老板摘要")
        self.compare_left_path = tk.StringVar()
        self.compare_right_path = tk.StringVar()
        self.last_compare_result = None
        self.last_missing = []
        self.last_extra = []
        self.last_shared = []
        self.search_results = []
        self.favorites = []
        self.recent_dirs = []
        self.compare_dialog = None
        self.assets_dialog = None
        self.ai_settings_dialog = None
        self._build_styles()
        self._build_ui()

    def _build_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("App.TFrame", background="#f3f6fb")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("Title.TLabel", background="#f3f6fb", foreground="#1f2a44", font=("Microsoft YaHei UI", 18, "bold"))
        self.style.configure("Section.TLabel", background="#ffffff", foreground="#23324d", font=("Microsoft YaHei UI", 10, "bold"))
        self.style.configure("Hint.TLabel", background="#ffffff", foreground="#5b6b88", font=("Microsoft YaHei UI", 8))
        self.style.configure("Primary.TButton", font=("Microsoft YaHei UI", 9))
        self.style.configure("SummaryValue.TLabel", background="#ffffff", foreground="#1f2a44", font=("Microsoft YaHei UI", 18, "bold"))
        self.style.configure("SummaryLabel.TLabel", background="#ffffff", foreground="#5b6b88", font=("Microsoft YaHei UI", 10))
        self.style.configure("Treeview", rowheight=30, font=("Microsoft YaHei UI", 10))
        self.style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_ui(self):
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=16)
        root_frame.pack(fill="both", expand=True)

        header_frame = ttk.Frame(root_frame, style="App.TFrame")
        header_frame.pack(fill="x", pady=(0, 12))
        top_line = ttk.Frame(header_frame, style="App.TFrame")
        top_line.pack(fill="x")
        ttk.Label(top_line, text="Windows 文件夹管理系统", style="Title.TLabel").pack(side="left", anchor="w")
        ttk.Label(top_line, text=APP_VERSION, style="Hint.TLabel").pack(side="left", padx=(10, 0), pady=(6, 0))
        ttk.Button(top_line, text="关于", command=self.show_about).pack(side="right")
        ttk.Label(header_frame, text="目录模板、结构扫描、文件检索、差异分析、AI 总结", style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        self.main_notebook = ttk.Notebook(root_frame)
        self.main_notebook.pack(fill="both", expand=True)

        project_tab = ttk.Frame(self.main_notebook, style="Card.TFrame", padding=14)
        workspace_tab = ttk.Frame(self.main_notebook, style="Card.TFrame", padding=14)
        self.main_notebook.add(project_tab, text="项目设置")
        self.main_notebook.add(workspace_tab, text="文件检索与对比")

        project_tab.columnconfigure(0, weight=1)
        project_tab.rowconfigure(5, weight=1)
        workspace_tab.columnconfigure(0, weight=1)
        workspace_tab.rowconfigure(6, weight=1)

        self._build_left_panel(project_tab)
        self._build_right_panel(workspace_tab)
        self.log("程序已启动。先选择目标文件夹，再进入对应页面操作。")

    def _build_left_panel(self, parent):
        ttk.Label(parent, text="项目设置", style="Section.TLabel").grid(row=0, column=0, sticky="w")

        folder_frame = ttk.Frame(parent, style="Card.TFrame")
        folder_frame.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        folder_frame.columnconfigure(1, weight=1)
        ttk.Label(folder_frame, text="目标文件夹", style="Hint.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(folder_frame, textvariable=self.target_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(folder_frame, text="选择文件夹", command=self.choose_folder, style="Primary.TButton").grid(row=0, column=2, padx=(8, 0))

        template_frame = ttk.Frame(parent, style="Card.TFrame")
        template_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        template_frame.columnconfigure(1, weight=1)
        ttk.Label(template_frame, text="模板类型", style="Hint.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.OptionMenu(template_frame, self.template_name, self.template_name.get(), *TEMPLATES.keys()).grid(row=0, column=1, sticky="w")
        ttk.Button(template_frame, text="加载模板", command=self.load_selected_template).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(template_frame, text="Help", command=self.show_help).grid(row=0, column=3, padx=(8, 0))

        ignore_frame = ttk.Frame(parent, style="Card.TFrame")
        ignore_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ignore_frame.columnconfigure(0, weight=1)
        ttk.Label(ignore_frame, text="忽略目录/文件（英文逗号分隔）", style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(ignore_frame, textvariable=self.ignore_names).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(ignore_frame, text="项目说明 / 备注", style="Hint.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(ignore_frame, textvariable=self.project_note).grid(row=3, column=0, sticky="ew", pady=(4, 0))

        action_frame = ttk.Frame(parent, style="Card.TFrame")
        action_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        for index in range(3):
            action_frame.columnconfigure(index, weight=1)
        ttk.Button(action_frame, text="初始化模板", command=self.init_template).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="生成结构", command=self.handle_create_structure).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="扫描结构", command=self.handle_scan_structure).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="反向生成模板", command=self.handle_reverse_generate).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="保存项目配置", command=self.handle_save_project_config).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="加载项目配置", command=self.handle_load_project_config).grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="一键补齐缺失项", command=self.handle_fill_missing).grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=4)

        settings_action_frame = ttk.Frame(parent, style="Card.TFrame")
        settings_action_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        settings_action_frame.columnconfigure(0, weight=1)
        settings_action_frame.columnconfigure(1, weight=1)
        ttk.Button(settings_action_frame, text="AI 接口设置", command=self.open_ai_settings_dialog).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(settings_action_frame, text="查看最近/收藏", command=self.open_assets_dialog).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(parent, text="File_list.md 编辑区", style="Section.TLabel").grid(row=6, column=0, sticky="w", pady=(2, 6))
        self.editor = scrolledtext.ScrolledText(parent, height=26, font=("Consolas", 10), bd=1, relief="solid")
        self.editor.grid(row=7, column=0, sticky="nsew")
        parent.rowconfigure(7, weight=1)
        self.editor.insert("1.0", DEFAULT_TEMPLATE)

    def _build_right_panel(self, parent):
        ttk.Label(parent, text="文件检索与对比", style="Section.TLabel").grid(row=0, column=0, sticky="w")

        toolbar = ttk.Frame(parent, style="Card.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="搜索关键词", style="Hint.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(toolbar, textvariable=self.search_keyword).grid(row=0, column=1, sticky="ew")
        ttk.Button(toolbar, text="搜索文件", command=self.handle_search_files).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(toolbar, text="显示全部文件", command=self.handle_show_all_files).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(toolbar, text="文件/文件夹对比", command=self.open_compare_dialog).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(toolbar, text="最近/收藏", command=self.open_assets_dialog).grid(row=0, column=5, padx=(8, 0))
        ttk.Button(toolbar, text="AI 设置", command=self.open_ai_settings_dialog).grid(row=0, column=6, padx=(8, 0))
        ttk.Button(toolbar, text="结构化结果", command=self.open_structured_compare_view).grid(row=0, column=7, padx=(8, 0))

        action_row = ttk.Frame(parent, style="Card.TFrame")
        action_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for index in range(6):
            action_row.columnconfigure(index, weight=1)
        ttk.Button(action_row, text="打开文件", command=self.handle_open_file).grid(row=0, column=0, sticky="ew", padx=3, pady=3)
        ttk.Button(action_row, text="定位文件夹", command=self.handle_locate_file).grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        ttk.Button(action_row, text="复制完整路径", command=self.handle_copy_full_path).grid(row=0, column=2, sticky="ew", padx=3, pady=3)
        ttk.Button(action_row, text="复制相对路径", command=self.handle_copy_relative_path).grid(row=0, column=3, sticky="ew", padx=3, pady=3)
        ttk.Button(action_row, text="加入收藏", command=self.handle_add_favorite).grid(row=0, column=4, sticky="ew", padx=3, pady=3)
        ttk.Button(action_row, text="发送到对比右侧", command=lambda: self.send_selected_to_compare('right')).grid(row=0, column=5, sticky="ew", padx=3, pady=3)

        columns = ("name", "relative_path", "size", "modified")
        search_table_frame = ttk.Frame(parent, style="Card.TFrame")
        search_table_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 12))
        search_table_frame.columnconfigure(0, weight=1)
        search_table_frame.rowconfigure(0, weight=1)
        self.search_tree = ttk.Treeview(search_table_frame, columns=columns, show="headings", height=14)
        self.search_tree.heading("name", text="文件名")
        self.search_tree.heading("relative_path", text="相对路径")
        self.search_tree.heading("size", text="大小")
        self.search_tree.heading("modified", text="修改时间")
        self.search_tree.column("name", width=180)
        self.search_tree.column("relative_path", width=460)
        self.search_tree.column("size", width=100)
        self.search_tree.column("modified", width=170)
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        search_scroll = ttk.Scrollbar(search_table_frame, orient="vertical", command=self.search_tree.yview)
        search_scroll.grid(row=0, column=1, sticky="ns")
        self.search_tree.configure(yscrollcommand=search_scroll.set)
        self.search_tree.bind("<Double-1>", self.handle_open_file)

        log_card = ttk.Frame(parent, style="Card.TFrame", padding=8)
        log_card.grid(row=4, column=0, sticky="nsew")
        parent.rowconfigure(3, weight=5)
        parent.rowconfigure(4, weight=2)

        ttk.Label(log_card, text="运行日志", style="Section.TLabel").pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(log_card, height=10, font=("Consolas", 9), bd=1, relief="solid")
        self.log_box.pack(fill="both", expand=True, pady=(6, 0))

    def get_base_dir(self) -> Path:
        value = self.target_dir.get().strip()
        if not value:
            raise ValueError("请先选择目标文件夹")
        base_dir = Path(value)
        if not base_dir.exists():
            raise ValueError("目标文件夹不存在")
        return base_dir

    def log(self, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "log_box") and self.log_box.winfo_exists():
            self.log_box.insert(tk.END, f"[{now}] {message}\n")
            self.log_box.see(tk.END)

    def log_compare_summary(self, result: dict):
        if result.get("mode") == "directory":
            self.log(f"目录对比完成：仅左侧 {len(result.get('left_only', []))} 项，仅右侧 {len(result.get('right_only', []))} 项，内容变更 {len(result.get('changed_files', []))} 项，一致 {len(result.get('same_files', []))} 项")
        elif result.get("mode") == "file":
            self.log(f"文件对比完成：状态={result.get('status')}；{result.get('summary', '')}")

    def send_selected_to_compare(self, side: str):
        row = self.get_selected_search_result()
        target = str(row["full_path"])
        if side == "left":
            self.compare_left_path.set(target)
            self.log(f"已将搜索结果发送到对比左侧：{target}")
        else:
            self.compare_right_path.set(target)
            self.log(f"已将搜索结果发送到对比右侧：{target}")

    def clear_search_results(self):
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_results = []

    def get_selected_search_result(self):
        selection = self.search_tree.selection()
        if not selection:
            raise ValueError("请先在搜索结果里选中一个文件")
        index = int(selection[0])
        return self.search_results[index]

    def choose_folder(self):
        folder = filedialog.askdirectory(title="选择目标文件夹")
        if folder:
            self.target_dir.set(folder)
            self.main_notebook.select(0)
            self.log(f"已选择目标文件夹：{folder}")
            self.handle_load_project_config(auto=True)
            file_list_path = Path(folder) / "File_list.md"
            if file_list_path.exists():
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", file_list_path.read_text(encoding="utf-8"))
                self.log("已加载现有 File_list.md")

    def load_selected_template(self):
        template = TEMPLATES.get(self.template_name.get(), DEFAULT_TEMPLATE)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", template)
        self.log(f"已载入模板：{self.template_name.get()}")

    def handle_save_project_config(self):
        try:
            base_dir = self.get_base_dir()
            config = {
                "app": "哈利 / 文件夹管理系统",
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "template_name": self.template_name.get(),
                "ignore_names": self.ignore_names.get().strip(),
                "project_note": self.project_note.get().strip(),
                "ai_base_url": self.ai_base_url.get().strip(),
                "ai_model": self.ai_model.get().strip(),
                "ai_api_key": self.ai_api_key.get().strip(),
            }
            config_path = save_project_config(base_dir, config)
            self.remember_recent_dir(str(base_dir))
            self.save_project_state(base_dir)
            self.log(f"项目配置已保存：{config_path}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def refresh_state_views(self):
        if hasattr(self, "recent_dirs_combo") and self.recent_dirs_combo.winfo_exists():
            self.recent_dirs_combo["values"] = self.recent_dirs
        if hasattr(self, "favorite_files_combo") and self.favorite_files_combo.winfo_exists():
            self.favorite_files_combo["values"] = [item["relative_path"] for item in self.favorites]

    def load_project_state(self, base_dir: Path):
        state = load_app_state(base_dir)
        self.favorites = state.get("favorites", [])
        self.recent_dirs = state.get("recent_dirs", [])
        self.refresh_state_views()

    def save_project_state(self, base_dir: Path):
        state = {
            "app": "哈利 / 文件夹管理系统",
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "favorites": self.favorites,
            "recent_dirs": self.recent_dirs[:10],
        }
        save_app_state(base_dir, state)

    def remember_recent_dir(self, folder: str):
        if folder in self.recent_dirs:
            self.recent_dirs.remove(folder)
        self.recent_dirs.insert(0, folder)
        self.recent_dirs = self.recent_dirs[:10]
        self.refresh_state_views()

    def handle_load_project_config(self, auto: bool = False):
        try:
            base_dir = self.get_base_dir()
            config = load_project_config(base_dir)
            self.load_project_state(base_dir)
            self.remember_recent_dir(str(base_dir))
            self.save_project_state(base_dir)
            if not config:
                if not auto:
                    self.log("未找到项目配置文件")
                return
            template_name = config.get("template_name")
            if template_name in TEMPLATES:
                self.template_name.set(template_name)
            self.ignore_names.set(config.get("ignore_names", DEFAULT_IGNORE))
            self.project_note.set(config.get("project_note", ""))
            self.ai_base_url.set(config.get("ai_base_url", self.ai_base_url.get()))
            self.ai_model.set(config.get("ai_model", self.ai_model.get()))
            self.ai_api_key.set(config.get("ai_api_key", self.ai_api_key.get()))
            if auto:
                self.log("已自动加载项目配置")
            else:
                self.log("已加载项目配置")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def open_ai_settings_dialog(self):
        self.main_notebook.select(1)
        if self.ai_settings_dialog and self.ai_settings_dialog.winfo_exists():
            self.ai_settings_dialog.lift()
            self.ai_settings_dialog.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.ai_settings_dialog = win
        win.title("AI 接口设置")
        win.geometry("760x320")
        win.minsize(680, 280)
        win.resizable(True, True)

        wrapper = ttk.Frame(win, style="App.TFrame", padding=14)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(1, weight=1)

        ttk.Label(wrapper, text="AI 接口设置", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(wrapper, text="兼容 OpenAI Chat Completions，可接多数国内兼容网关", style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 10))
        ttk.Label(wrapper, text="API Base URL", style="Hint.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Entry(wrapper, textvariable=self.ai_base_url).grid(row=2, column=1, sticky="ew")
        ttk.Label(wrapper, text="Model", style="Hint.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(wrapper, textvariable=self.ai_model).grid(row=3, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(wrapper, text="摘要模式", style="Hint.TLabel").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(wrapper, textvariable=self.ai_summary_mode, state="readonly", values=["老板摘要", "技术摘要", "简洁摘要"]).grid(row=4, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(wrapper, text="API Key", style="Hint.TLabel").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(wrapper, textvariable=self.ai_api_key, show="*").grid(row=5, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(wrapper, text="测试连接", command=self.handle_test_ai_connection).grid(row=2, column=2, rowspan=2, padx=(8, 0), sticky="nsew")
        ttk.Button(wrapper, text="保存到项目配置", command=self.handle_save_project_config).grid(row=5, column=2, padx=(8, 0), sticky="ew", pady=(8, 0))

    def open_assets_dialog(self):
        self.main_notebook.select(1)
        if self.assets_dialog and self.assets_dialog.winfo_exists():
            self.assets_dialog.lift()
            self.assets_dialog.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.assets_dialog = win
        win.title("最近目录 / 收藏文件")
        win.geometry("820x420")
        win.minsize(720, 320)
        win.resizable(True, True)

        wrapper = ttk.Frame(win, style="App.TFrame", padding=14)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(1, weight=1)

        ttk.Label(wrapper, text="最近目录 / 收藏文件", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(wrapper, text="把低频但常用的辅助入口收纳到弹窗里", style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 10))
        ttk.Label(wrapper, text="最近目录", style="Hint.TLabel").grid(row=2, column=0, sticky="w")
        self.recent_dirs_combo = ttk.Combobox(wrapper, state="readonly", values=self.recent_dirs)
        self.recent_dirs_combo.grid(row=2, column=1, sticky="ew")
        ttk.Button(wrapper, text="打开最近目录", command=self.handle_open_recent_dir).grid(row=2, column=2, padx=(8, 0))

        ttk.Label(wrapper, text="收藏文件", style="Hint.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.favorite_files_combo = ttk.Combobox(wrapper, state="readonly", values=[item["relative_path"] for item in self.favorites])
        self.favorite_files_combo.grid(row=3, column=1, sticky="ew", pady=(10, 0))
        action_bar = ttk.Frame(wrapper, style="App.TFrame")
        action_bar.grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=(10, 0))
        ttk.Button(action_bar, text="打开收藏", command=self.handle_open_favorite).pack(fill="x")
        ttk.Button(action_bar, text="移除收藏", command=self.handle_remove_favorite).pack(fill="x", pady=(8, 0))

    def open_compare_dialog(self):
        self.main_notebook.select(1)
        if self.compare_dialog and self.compare_dialog.winfo_exists():
            self.compare_dialog.lift()
            self.compare_dialog.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.compare_dialog = win
        win.title("文件 / 文件夹对比")
        win.geometry("1420x900")
        win.minsize(1180, 760)
        win.resizable(True, True)

        wrapper = ttk.Frame(win, style="App.TFrame", padding=14)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(3, weight=3)
        wrapper.rowconfigure(4, weight=2)

        ttk.Label(wrapper, text="文件 / 文件夹对比", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(wrapper, text="左旧右新：左侧默认看 OLD / 基准，右侧默认看 NEW / 当前 + diff，下方专门看 AI 结论。", style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 10))

        control = ttk.Frame(wrapper, style="Card.TFrame", padding=10)
        control.grid(row=2, column=0, sticky="ew")
        control.columnconfigure(1, weight=5)
        control.columnconfigure(4, weight=3)

        ttk.Label(control, text="左旧右新｜绿色=新增｜红色=删除｜蓝色=文件头｜紫色=变更块", style="Hint.TLabel").grid(row=0, column=7, rowspan=2, sticky="e", padx=(12, 0))

        ttk.Label(control, text="左侧路径", style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(control, textvariable=self.compare_left_path).grid(row=0, column=1, sticky="ew")
        ttk.Button(control, text="选文件", command=lambda: self.pick_compare_path('left', False)).grid(row=0, column=2, padx=4)
        ttk.Button(control, text="选文件夹", command=lambda: self.pick_compare_path('left', True)).grid(row=0, column=3, padx=4)
        ttk.Button(control, text="从搜索结果选中", command=lambda: self.send_selected_to_compare('left')).grid(row=0, column=4, padx=4, sticky="ew")
        ttk.Button(control, text="执行对比", command=self.handle_workspace_compare).grid(row=0, column=5, rowspan=2, sticky="nsew", padx=(8, 0))
        ttk.Button(control, text="AI 总结差异", command=self.handle_ai_compare_summary).grid(row=0, column=6, rowspan=2, sticky="nsew", padx=(8, 0))

        ttk.Label(control, text="右侧路径", style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(control, textvariable=self.compare_right_path).grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(control, text="选文件", command=lambda: self.pick_compare_path('right', False)).grid(row=1, column=2, padx=4, pady=(10, 0))
        ttk.Button(control, text="选文件夹", command=lambda: self.pick_compare_path('right', True)).grid(row=1, column=3, padx=4, pady=(10, 0))
        ttk.Button(control, text="从搜索结果选中", command=lambda: self.send_selected_to_compare('right')).grid(row=1, column=4, padx=4, pady=(10, 0), sticky="ew")

        content_panes = ttk.Panedwindow(wrapper, orient=tk.HORIZONTAL)
        content_panes.grid(row=3, column=0, sticky="nsew", pady=(12, 0))

        left_card = ttk.Frame(content_panes, style="Card.TFrame", padding=8)
        right_card = ttk.Frame(content_panes, style="Card.TFrame", padding=8)
        content_panes.add(left_card, weight=1)
        content_panes.add(right_card, weight=1)

        ttk.Label(left_card, text="左侧（OLD / 基准）", style="Section.TLabel").pack(anchor="w")
        self.compare_left_box = scrolledtext.ScrolledText(left_card, font=("Consolas", 10), bd=1, relief="solid")
        self.compare_left_box.pack(fill="both", expand=True, pady=(6, 0))

        ttk.Label(right_card, text="右侧（NEW / 当前 / diff）", style="Section.TLabel").pack(anchor="w")
        self.compare_right_box = scrolledtext.ScrolledText(right_card, font=("Consolas", 10), bd=1, relief="solid")
        self.compare_right_box.pack(fill="both", expand=True, pady=(6, 0))

        ai_card = ttk.Frame(wrapper, style="Card.TFrame", padding=8)
        ai_card.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(ai_card, text="AI 差异总结", style="Section.TLabel").pack(anchor="w")
        ttk.Label(ai_card, text="这里是主结果区，优先给出结论、风险和建议复核项。", style="Hint.TLabel").pack(anchor="w", pady=(2, 6))
        self.ai_summary_box = scrolledtext.ScrolledText(ai_card, font=("Microsoft YaHei UI", 10), bd=1, relief="solid", wrap=tk.WORD)
        self.ai_summary_box.pack(fill="both", expand=True)

        self.diff_box = self.compare_right_box
    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title(f"使用帮助 - {APP_NAME}")
        help_window.geometry("860x700")
        help_window.configure(bg="#f3f6fb")
        wrapper = ttk.Frame(help_window, style="App.TFrame", padding=12)
        wrapper.pack(fill="both", expand=True)
        ttk.Label(wrapper, text="使用帮助", style="Title.TLabel").pack(anchor="w")
        ttk.Label(wrapper, text="适合第一次使用的同事，按步骤照着做就行", style="Hint.TLabel").pack(anchor="w", pady=(4, 10))
        help_box = scrolledtext.ScrolledText(wrapper, font=("Microsoft YaHei UI", 11), wrap=tk.WORD, bd=1, relief="solid")
        help_box.pack(fill="both", expand=True)
        help_box.insert("1.0", HELP_TEXT)
        help_box.config(state="disabled")

    def show_about(self):
        about_text = f"""{APP_NAME} {APP_VERSION}

开发标识：哈利 / 文件夹管理系统

这是一个面向本地项目资料治理的桌面工具，核心目标是让项目目录：
- 有标准
- 能扫描
- 可比对
- 可补齐
- 好查找
- 易交接

当前重点能力：
- 模板建目录
- 结构扫描
- 差异检查
- 一键补齐
- 文件搜索
- 文件/文件夹差异对比
- AI 差异总结
- 收藏文件
- 最近目录
- 项目配置保存

适合场景：
- 项目资料整理
- 研发目录规范
- 交付资料归档
- 团队协作接手
"""
        messagebox.showinfo("关于", about_text)

    def init_template(self):
        try:
            base_dir = self.get_base_dir()
            file_list_path = base_dir / "File_list.md"
            if not file_list_path.exists():
                file_list_path.write_text(self.editor.get("1.0", tk.END).strip() + "\n", encoding="utf-8")
                self.log(f"已创建模板文件：{file_list_path}")
            else:
                self.log("File_list.md 已存在，未覆盖")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def load_entries(self):
        content = self.editor.get("1.0", tk.END)
        entries = parse_file_list(content)
        if not entries:
            raise ValueError("File_list.md 内容为空或格式无效")
        return entries

    def handle_create_structure(self):
        try:
            base_dir = self.get_base_dir()
            entries = self.load_entries()
            actions = create_structure(base_dir, entries)
            (base_dir / "File_list.md").write_text(self.editor.get("1.0", tk.END).strip() + "\n", encoding="utf-8")
            self.log(f"已根据 File_list.md 生成结构，共处理 {len(actions)} 项")
            for item in actions[:80]:
                self.log(item)
            if len(actions) > 80:
                self.log(f"其余 {len(actions) - 80} 项未展开显示")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_scan_structure(self):
        try:
            base_dir = self.get_base_dir()
            ignore_names = parse_ignore_list(self.ignore_names.get())
            snapshot_path = save_snapshot(base_dir, ignore_names)
            self.log(f"目录结构已输出到：{snapshot_path}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_compare(self):
        try:
            base_dir = self.get_base_dir()
            entries = self.load_entries()
            ignore_names = parse_ignore_list(self.ignore_names.get())
            log_path, missing, extra = compare_structure(base_dir, entries, ignore_names)
            expected = expected_relative_structure(entries)
            actual = collect_relative_structure(base_dir, ignore_names)
            shared = sorted(expected & actual)
            self.show_diff(missing, extra, shared)
            self.log(f"对比完成：缺失 {len(missing)} 项，多余 {len(extra)} 项，匹配 {len(shared)} 项")
            self.log(f"差异日志已保存：{log_path}")
            for item in missing[:20]:
                self.log(f"缺失：{item}")
            for item in extra[:20]:
                self.log(f"多余：{item}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_reverse_generate(self):
        try:
            base_dir = self.get_base_dir()
            ignore_names = parse_ignore_list(self.ignore_names.get())
            content = generate_template_from_directory(base_dir, ignore_names)
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.log("已根据当前目录反向生成 File_list 模板")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_fill_missing(self):
        try:
            base_dir = self.get_base_dir()
            entries = self.load_entries()
            ignore_names = parse_ignore_list(self.ignore_names.get())
            _, missing, extra = compare_structure(base_dir, entries, ignore_names)
            if not missing:
                self.show_diff(missing, extra, sorted(expected_relative_structure(entries) & collect_relative_structure(base_dir, ignore_names)))
                self.log("没有缺失项，无需补齐")
                return

            expected_map = {entry['path'].as_posix() + ('/' if entry['is_dir'] else ''): entry for entry in entries}
            fill_entries = [expected_map[item] for item in missing if item in expected_map]
            actions = create_structure(base_dir, fill_entries)
            updated_actual = collect_relative_structure(base_dir, ignore_names)
            updated_shared = sorted(expected_relative_structure(entries) & updated_actual)
            self.show_diff([], extra, updated_shared)
            self.log(f"已一键补齐缺失项，共处理 {len(actions)} 项")
            for item in actions[:40]:
                self.log(item)
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def run_file_search(self, keyword_text: str, show_empty_result_message: bool = True):
        base_dir = self.get_base_dir()
        keyword = keyword_text.strip().lower()
        keywords = [item for item in keyword.split() if item]
        ignore_names = parse_ignore_list(self.ignore_names.get())
        self.clear_search_results()
        scanned_files = 0

        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [directory for directory in dirs if directory not in ignore_names]
            for file_name in files:
                if file_name in ignore_names:
                    continue

                full_path = Path(root) / file_name
                relative_path = full_path.relative_to(base_dir).as_posix()
                searchable_text = f"{file_name} {relative_path}".lower()
                scanned_files += 1

                if keywords and not all(item in searchable_text for item in keywords):
                    continue

                stat = full_path.stat()
                row = {
                    "name": file_name,
                    "relative_path": relative_path,
                    "full_path": full_path,
                    "size": format_file_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "is_text_like": is_text_like_file(full_path),
                }
                self.search_results.append(row)

        for index, row in enumerate(self.search_results):
            self.search_tree.insert("", "end", iid=str(index), values=(row["name"], row["relative_path"], row["size"], row["modified"]))

        self.log(f"搜索目录：{base_dir}")
        self.log(f"已扫描文件数：{scanned_files}")
        self.log(f"搜索关键词：{keyword or '（空，返回全部文件）'}")
        if self.search_results:
            text_like = sum(1 for item in self.search_results if item.get("is_text_like"))
            self.log(f"搜索完成，共找到 {len(self.search_results)} 个匹配文件")
            self.log(f"搜索结果统计：{len(self.search_results)} 项，其中可直接做文本对比的文件 {text_like} 项")
        else:
            self.log("未找到匹配文件，请检查关键词、目标文件夹或忽略规则")
            self.log("搜索结果统计：0 项")
            if show_empty_result_message:
                messagebox.showinfo("搜索结果", "未找到匹配文件。\n\n请检查：\n1. 目标文件夹是否选对\n2. 关键词是否为文件名或路径片段\n3. 忽略规则是否把目标目录过滤掉")

    def pick_compare_path(self, side: str, choose_dir: bool):
        path = filedialog.askdirectory(title="选择文件夹") if choose_dir else filedialog.askopenfilename(title="选择文件")
        if not path:
            return
        if side == "left":
            self.compare_left_path.set(path)
        else:
            self.compare_right_path.set(path)
        if self.compare_dialog and self.compare_dialog.winfo_exists():
            self.compare_dialog.lift()
            self.compare_dialog.focus_force()

    def show_compare_result(self, result: dict):
        self.last_compare_result = result
        left_box = getattr(self, "compare_left_box", None)
        right_box = getattr(self, "compare_right_box", None)
        if left_box and left_box.winfo_exists():
            left_box.delete("1.0", tk.END)
        if right_box and right_box.winfo_exists():
            right_box.delete("1.0", tk.END)

        if result.get("mode") == "file":
            if left_box and left_box.winfo_exists():
                left_box.insert(tk.END, result.get("left_excerpt", ""))
            if right_box and right_box.winfo_exists():
                right_box.insert(tk.END, result.get("right_excerpt", ""))
                right_box.insert(tk.END, "\n\n[内容差异]\n", "section")
                right_box.insert(tk.END, result.get("diff_text", "") + ("\n" if result.get("diff_text") else ""))
            if hasattr(self, "ai_summary_box") and self.ai_summary_box.winfo_exists():
                self.ai_summary_box.delete("1.0", tk.END)
                self.ai_summary_box.insert(tk.END, "请点击“AI 总结差异”生成面向老板 / 技术 / 简洁模式的结论。")
        else:
            if left_box and left_box.winfo_exists():
                left_box.insert(tk.END, "[仅左侧存在]\n")
                for item in result.get("left_only", []):
                    left_box.insert(tk.END, f"- {item}\n")
                left_box.insert(tk.END, "\n[完全一致文件]\n")
                for item in result.get("same_files", [])[:200]:
                    left_box.insert(tk.END, f"- {item}\n")
            if right_box and right_box.winfo_exists():
                right_box.insert(tk.END, "[仅右侧存在]\n")
                for item in result.get("right_only", []):
                    right_box.insert(tk.END, f"- {item}\n")
                right_box.insert(tk.END, "\n[内容变更文件]\n", "section")
                for item in result.get("changed_files", []):
                    right_box.insert(tk.END, f"- {item}\n")
                right_box.insert(tk.END, "\n[汇总]\n" + result.get("summary", "") + "\n")
            if hasattr(self, "ai_summary_box") and self.ai_summary_box.winfo_exists():
                self.ai_summary_box.delete("1.0", tk.END)
                self.ai_summary_box.insert(tk.END, "请点击“AI 总结差异”生成目录变化总结、风险点与建议复核项。")

        if right_box and right_box.winfo_exists():
            self.diff_box = right_box
            self.apply_diff_highlight()

    def apply_diff_highlight(self):
        self.diff_box.tag_config("diff_add", foreground="#2e7d32")
        self.diff_box.tag_config("diff_remove", foreground="#c62828")
        self.diff_box.tag_config("diff_meta", foreground="#1565c0")
        self.diff_box.tag_config("diff_hunk", foreground="#6a1b9a")
        content = self.diff_box.get("1.0", tk.END)
        for idx, line in enumerate(content.splitlines(), start=1):
            if line.startswith("+++") or line.startswith("---"):
                self.diff_box.tag_add("diff_meta", f"{idx}.0", f"{idx}.end")
            elif line.startswith("@@"):
                self.diff_box.tag_add("diff_hunk", f"{idx}.0", f"{idx}.end")
            elif line.startswith("+") and not line.startswith("+++"):
                self.diff_box.tag_add("diff_add", f"{idx}.0", f"{idx}.end")
            elif line.startswith("-") and not line.startswith("---"):
                self.diff_box.tag_add("diff_remove", f"{idx}.0", f"{idx}.end")

    def handle_workspace_compare(self):
        try:
            left = Path(self.compare_left_path.get().strip())
            right = Path(self.compare_right_path.get().strip())
            if not left or not right or str(left) == '.' or str(right) == '.':
                raise ValueError("请先选择左右两侧的文件或文件夹")
            ignore_names = parse_ignore_list(self.ignore_names.get())
            if left.is_dir() and right.is_dir():
                result = compare_two_directories(left, right, ignore_names)
            elif left.is_file() and right.is_file():
                result = compare_two_files(left, right)
            else:
                raise ValueError("左右两侧类型必须一致：要么都选文件，要么都选文件夹")
            self.show_compare_result(result)
            self.log_compare_summary(result)
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def open_structured_compare_view(self):
        if not self.last_compare_result:
            messagebox.showinfo("提示", "请先执行一次对比")
            return
        win = tk.Toplevel(self.root)
        win.title("结构化对比结果")
        win.geometry("960x620")
        wrapper = ttk.Frame(win, style="App.TFrame", padding=14)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(1, weight=1)
        ttk.Label(wrapper, text="结构化对比结果", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(wrapper, text="左旧右新：左侧=OLD / 基准，右侧=NEW / 当前。", style="Hint.TLabel").grid(row=0, column=0, sticky="e")
        columns = ("category", "path")
        tree = ttk.Treeview(wrapper, columns=columns, show="headings")
        tree.heading("category", text="类别")
        tree.heading("path", text="路径 / 内容")
        tree.column("category", width=140)
        tree.column("path", width=760)
        tree.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        data = self.last_compare_result
        if data.get("mode") == "directory":
            for item in data.get("left_only", []):
                tree.insert("", "end", values=("仅左侧存在", item))
            for item in data.get("right_only", []):
                tree.insert("", "end", values=("仅右侧存在", item))
            for item in data.get("changed_files", []):
                tree.insert("", "end", values=("内容变更", item))
            for item in data.get("same_files", [])[:300]:
                tree.insert("", "end", values=("完全一致", item))
        else:
            diff_lines = data.get("diff_text", "").splitlines()
            for line in diff_lines[:500]:
                category = "变更"
                if line.startswith("+++") or line.startswith("---"):
                    category = "文件头"
                elif line.startswith("@@"):
                    category = "变更块"
                elif line.startswith("+") and not line.startswith("+++"):
                    category = "新增行"
                elif line.startswith("-") and not line.startswith("---"):
                    category = "删除行"
                tree.insert("", "end", values=(category, line))

    def handle_ai_compare_summary(self):
        try:
            if not self.last_compare_result:
                raise ValueError("请先执行一次文件/文件夹对比")
            base_url = self.ai_base_url.get().strip()
            model = self.ai_model.get().strip()
            api_key = self.ai_api_key.get().strip()
            if not base_url or not model:
                raise ValueError("请先填写 AI 接口配置（Base URL / Model）")
            prompt = build_ai_messages_from_compare(self.last_compare_result, self.ai_summary_mode.get())
            self.log("正在调用 AI 生成差异总结，请稍候...")
            content = call_openai_compatible_api(base_url, api_key, model, prompt, timeout=90)
            if hasattr(self, "ai_summary_box") and self.ai_summary_box.winfo_exists():
                self.ai_summary_box.delete("1.0", tk.END)
                self.ai_summary_box.insert(tk.END, content + "\n")
            else:
                self.diff_box.insert(tk.END, "\n\n[AI 总结]\n", "section")
                self.diff_box.insert(tk.END, content + "\n")
            self.log("AI 差异总结已生成")
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', errors='ignore')
            messagebox.showerror("AI 接口错误", f"HTTP {error.code}\n{detail}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_test_ai_connection(self):
        try:
            base_url = self.ai_base_url.get().strip()
            model = self.ai_model.get().strip()
            api_key = self.ai_api_key.get().strip()
            if not base_url or not model:
                raise ValueError("请先填写 API Base URL 和 Model")
            content = call_openai_compatible_api(base_url, api_key, model, "请只回复：连接成功", timeout=45)
            self.log(f"AI 接口测试成功：{content[:120]}")
            messagebox.showinfo("成功", f"AI 接口测试成功\n\n返回：{content[:200]}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', errors='ignore')
            messagebox.showerror("AI 接口错误", f"HTTP {error.code}\n{detail}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_search_files(self):
        try:
            self.run_file_search(self.search_keyword.get(), show_empty_result_message=True)
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_show_all_files(self):
        try:
            self.search_keyword.set("")
            self.run_file_search("", show_empty_result_message=False)
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_open_file(self, event=None):
        try:
            row = self.get_selected_search_result()
            if open_with_default_app(row["full_path"]):
                self.log(f"已打开文件：{row['full_path']}")
            else:
                self.log(f"打开失败：{row['full_path']}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_locate_file(self):
        try:
            row = self.get_selected_search_result()
            if open_in_system_explorer(row["full_path"].parent):
                self.log(f"已定位文件夹：{row['full_path'].parent}")
            else:
                self.log(f"定位失败：{row['full_path'].parent}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_copy_full_path(self):
        try:
            row = self.get_selected_search_result()
            self.root.clipboard_clear()
            self.root.clipboard_append(str(row["full_path"]))
            self.root.update()
            self.log(f"已复制完整路径：{row['full_path']}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_copy_relative_path(self):
        try:
            row = self.get_selected_search_result()
            self.root.clipboard_clear()
            self.root.clipboard_append(row["relative_path"])
            self.root.update()
            self.log(f"已复制相对路径：{row['relative_path']}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_add_favorite(self):
        try:
            base_dir = self.get_base_dir()
            row = self.get_selected_search_result()
            favorite = {
                "relative_path": row["relative_path"],
                "full_path": str(row["full_path"]),
            }
            self.favorites = [item for item in self.favorites if item.get("relative_path") != row["relative_path"]]
            self.favorites.insert(0, favorite)
            self.favorites = self.favorites[:30]
            self.refresh_state_views()
            self.save_project_state(base_dir)
            self.log(f"已加入收藏：{row['relative_path']}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def get_selected_favorite(self):
        selected = self.favorite_files_combo.get().strip()
        if not selected:
            raise ValueError("请先在收藏文件里选中一个项目")
        for item in self.favorites:
            if item.get("relative_path") == selected:
                return item
        raise ValueError("未找到对应收藏项")

    def handle_open_favorite(self):
        try:
            favorite = self.get_selected_favorite()
            target_path = Path(favorite["full_path"])
            if open_with_default_app(target_path):
                self.log(f"已打开收藏文件：{target_path}")
            else:
                self.log(f"打开收藏文件失败：{target_path}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_remove_favorite(self):
        try:
            base_dir = self.get_base_dir()
            favorite = self.get_selected_favorite()
            self.favorites = [item for item in self.favorites if item.get("relative_path") != favorite.get("relative_path")]
            self.refresh_state_views()
            self.save_project_state(base_dir)
            self.log(f"已移除收藏：{favorite['relative_path']}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_open_recent_dir(self):
        try:
            folder = self.recent_dirs_combo.get().strip()
            if not folder:
                raise ValueError("请先在最近目录里选中一个项目")
            if not Path(folder).exists():
                raise ValueError("最近目录已不存在")
            self.main_notebook.select(1)
            self.target_dir.set(folder)
            self.handle_load_project_config(auto=True)
            file_list_path = Path(folder) / "File_list.md"
            if file_list_path.exists():
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", file_list_path.read_text(encoding="utf-8"))
            self.log(f"已打开最近目录：{folder}")
        except Exception as error:
            messagebox.showerror("错误", str(error))

    def handle_open_selected_path(self, event=None):
        try:
            base_dir = self.get_base_dir()
            line = self.diff_box.get("insert linestart", "insert lineend").strip()
            if not line.startswith("-"):
                return
            relative_path = line[1:].strip().rstrip("/")
            if not relative_path or relative_path == "无":
                return
            target_path = base_dir / Path(relative_path)
            open_target = target_path if target_path.exists() else target_path.parent
            if open_in_system_explorer(open_target):
                self.log(f"已尝试定位：{open_target}")
            else:
                self.log(f"定位失败：{open_target}")
        except Exception as error:
            messagebox.showerror("错误", str(error))


if __name__ == "__main__":
    root = tk.Tk()
    app = FolderManagerApp(root)
    root.mainloop()
