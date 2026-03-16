import asyncio
import json
import os
import re
import shutil
import zipfile

import flet as ft


async def main(page: ft.Page):
    # =========================================================
    # 1. 页面基础设置
    # =========================================================
    page.title = "智能解压器"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0F172A"
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    if page.platform != ft.PagePlatform.ANDROID:
        page.window.width = 430
        page.window.height = 920

    # =========================================================
    # 2. 颜色与样式
    # =========================================================
    BG = "#0F172A"
    PANEL = "#111827"
    PANEL_2 = "#1F2937"
    PANEL_3 = "#0B1220"
    BORDER = "#334155"
    TEXT = "#E5E7EB"
    TEXT_SOFT = "#94A3B8"
    PRIMARY = "#2563EB"
    PRIMARY_LIGHT = "#60A5FA"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    DANGER = "#EF4444"
    FOLDER = "#FBBF24"

    # =========================================================
    # 3. 状态变量
    # =========================================================
    selected_file_paths = set()
    manual_selected_paths = set()
    successful_paths = set()
    current_tab = "scan"
    current_browse_path = ""
    last_scan_count = 0
    extracted_item_count = 0

    # =========================================================
    # 4. 路径与配置
    # =========================================================
    def get_root_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0"
        return os.path.expanduser("~")

    def get_download_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/Download"
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def get_output_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/QQ解压的视频文件"
        return os.path.join(os.path.expanduser("~"), "Desktop", "QQ解压的视频文件")

    def get_config_path() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/extractor_config.json"
        return os.path.join(os.path.expanduser("~"), ".extractor_config.json")

    def save_last_browse_path(path: str):
        try:
            with open(get_config_path(), "w", encoding="utf-8") as f:
                json.dump({"last_browse_path": path}, f, ensure_ascii=False)
        except Exception:
            pass

    def load_last_browse_path(default_path: str) -> str:
        try:
            config_path = get_config_path()
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                saved_path = str(data.get("last_browse_path", "")).strip()
                if saved_path and os.path.exists(saved_path) and os.path.isdir(saved_path):
                    return saved_path
        except Exception:
            pass
        return default_path

    current_browse_path = load_last_browse_path(get_download_dir())

    # =========================================================
    # 5. 安全刷新 & 安卓权限管理核心 (关键修复)
    # =========================================================
    def safe_update():
        try:
            page.update()
        except Exception:
            pass

    # 引入 Flet 官方权限管理器
    ph = ft.PermissionHandler()
    page.overlay.append(ph)

    def request_android_permissions(e=None):
        try:
            # 向系统申请最高级的【所有文件管理权限】（为了读取隐藏的 xls）
            ph.request_permission(ft.PermissionType.MANAGE_EXTERNAL_STORAGE)
        except Exception:
            pass
        try:
            # 兼容申请普通存储权限
            ph.request_permission(ft.PermissionType.STORAGE)
        except Exception:
            pass

    permission_btn = ft.Container(
        width=380,
        bgcolor=DANGER,
        border_radius=18,
        padding=14,
        ink=True,
        on_click=request_android_permissions,
        visible=page.platform == ft.PagePlatform.ANDROID, # 仅在安卓端显示
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SHIELD_ROUNDED, color=ft.Colors.WHITE, size=20),
                ft.Text("安卓必点：授予【所有文件访问】权限", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        )
    )

    # =========================================================
    # 6. 顶部信息区
    # =========================================================
    app_icon = ft.Container(
        width=46,
        height=46,
        border_radius=14,
        bgcolor=PRIMARY,
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(ft.Icons.ARCHIVE_ROUNDED, color=ft.Colors.WHITE, size=24),
    )

    app_title = ft.Text(
        "智能解压器",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=TEXT,
    )

    app_subtitle = ft.Text(
        "扫描 Download / QQfile_recv 并提取密码解压",
        size=12,
        color=TEXT_SOFT,
    )

    header_section = ft.Container(
        width=380,
        bgcolor=PANEL,
        border_radius=18,
        border=ft.Border.all(1, BORDER),
        padding=16,
        content=ft.Row(
            [
                app_icon,
                ft.Column(
                    [app_title, app_subtitle],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # =========================================================
    # 7. 统计卡片
    # =========================================================
    stat_found_value = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=TEXT)
    stat_selected_value = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=TEXT)
    stat_output_value = ft.Text("未开始", size=14, weight=ft.FontWeight.W_600, color=TEXT)

    def make_stat_card(title: str, value_control: ft.Control, icon_name: str):
        return ft.Container(
            expand=True,
            bgcolor=PANEL,
            border_radius=16,
            border=ft.Border.all(1, BORDER),
            padding=14,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon_name, size=16, color=PRIMARY_LIGHT),
                            ft.Text(title, size=12, color=TEXT_SOFT),
                        ],
                        spacing=6,
                    ),
                    value_control,
                ],
                spacing=10,
            ),
        )

    stats_section = ft.Row(
        [
            make_stat_card("扫描结果", stat_found_value, ft.Icons.SEARCH),
            make_stat_card("当前已选", stat_selected_value, ft.Icons.CHECK_CIRCLE_OUTLINE),
            make_stat_card("输出状态", stat_output_value, ft.Icons.FOLDER_OPEN),
        ],
        spacing=10,
        width=380,
    )

    # =========================================================
    # 8. 状态区
    # =========================================================
    status_title = ft.Text("当前状态", size=13, color=TEXT_SOFT)
    status_text = ft.Text(
        "等待操作",
        size=15,
        color=TEXT,
        weight=ft.FontWeight.W_500,
    )
    progress_bar = ft.ProgressBar(width=340, value=0, visible=False, color=PRIMARY)

    output_dir_text = ft.Text(
        f"输出目录：{get_output_dir()}",
        size=11,
        color=TEXT_SOFT,
        no_wrap=True,
    )

    status_section = ft.Container(
        width=380,
        bgcolor=PANEL,
        border_radius=18,
        border=ft.Border.all(1, BORDER),
        padding=16,
        content=ft.Column(
            [
                status_title,
                status_text,
                progress_bar,
                output_dir_text,
            ],
            spacing=10,
        ),
    )

    # =========================================================
    # 9. 通用卡片方法
    # =========================================================
    def make_click_card(
        title: str,
        icon_name: str,
        on_click=None,
        bgcolor=PANEL_2,
        icon_color=ft.Colors.WHITE,
        text_color=TEXT,
        subtitle: str = "",
        data=None,
        trailing=None,
    ):
        subtitle_control = (
            ft.Text(subtitle, size=11, color=TEXT_SOFT, no_wrap=True)
            if subtitle
            else ft.Container(height=0)
        )

        return ft.Container(
            data=data,
            on_click=on_click,
            bgcolor=bgcolor,
            border_radius=14,
            border=ft.Border.all(1, BORDER),
            padding=12,
            content=ft.Row(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=10,
                        bgcolor=PANEL_3,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(icon_name, size=18, color=icon_color),
                    ),
                    ft.Column(
                        [
                            ft.Text(title, size=14, color=text_color, no_wrap=True),
                            subtitle_control,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    trailing if trailing else ft.Container(width=0),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # =========================================================
    # 10. 弹窗
    # =========================================================
    def close_dlg(e=None):
        delete_dialog.open = False
        safe_update()

    def delete_source_file(e=None):
        deleted_count = 0
        for path in list(successful_paths):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted_count += 1
                selected_file_paths.discard(path)
                manual_selected_paths.discard(path)
            except Exception:
                pass

        delete_dialog.open = False
        set_status(f"已删除 {deleted_count} 个源文件", SUCCESS)
        refresh_manual_picked_list()
        load_directory(current_browse_path)
        safe_update()
        page.run_task(scan_files)

    delete_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("解压完成"),
        content=ft.Text("是否删除原始压缩包以释放空间？"),
        actions=[
            ft.Button("保留文件", on_click=close_dlg),
            ft.Button("删除源文件", on_click=delete_source_file),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(delete_dialog)

    # =========================================================
    # 11. 工具函数
    # =========================================================
    def set_status(message: str, color: str = TEXT):
        status_text.value = message
        status_text.color = color
        safe_update()

    def get_current_selected_count() -> int:
        return len(selected_file_paths) if current_tab == "scan" else len(manual_selected_paths)

    def update_stat_cards():
        selected_count = get_current_selected_count()
        stat_found_value.value = str(last_scan_count)
        stat_selected_value.value = str(selected_count)
        stat_output_value.value = "已输出" if extracted_item_count > 0 else "未开始"
        safe_update()

    def get_active_paths():
        return list(selected_file_paths) if current_tab == "scan" else list(manual_selected_paths)

    # =========================================================
    # 12. 选中区
    # =========================================================
    selected_list_view = ft.ListView(spacing=8, auto_scroll=False, expand=True)

    def refresh_manual_picked_list():
        selected_list_view.controls.clear()

        current_selected = sorted(manual_selected_paths)
        if not current_selected:
            selected_list_view.controls.append(
                ft.Container(
                    padding=10,
                    content=ft.Text("还没有选择文件", color=TEXT_SOFT),
                )
            )
            safe_update()
            return

        for path in current_selected:
            file_name = os.path.basename(path)

            remove_btn = ft.Container(
                width=28,
                height=28,
                border_radius=8,
                bgcolor="#3F1D1D",
                alignment=ft.Alignment(0, 0),
                on_click=lambda e, p=path: toggle_manual_file(p),
                content=ft.Icon(ft.Icons.CLOSE, size=16, color=DANGER),
            )

            selected_list_view.controls.append(
                make_click_card(
                    title=file_name,
                    icon_name=ft.Icons.CHECK_CIRCLE,
                    bgcolor=PANEL_2,
                    icon_color=SUCCESS,
                    subtitle=path,
                    trailing=remove_btn,
                )
            )

        safe_update()

    # =========================================================
    # 13. 列表控件
    # =========================================================
    file_list_view = ft.ListView(spacing=8, auto_scroll=False, expand=True)
    explorer_list_view = ft.ListView(spacing=8, auto_scroll=False, expand=True)

    current_path_text = ft.Text(
        current_browse_path,
        size=12,
        color=TEXT,
        expand=True,
        no_wrap=True,
    )

    # =========================================================
    # 14. 密码模式区
    # =========================================================
    password_mode = ft.RadioGroup(
        value="auto",
        content=ft.Row(
            [
                ft.Radio(value="auto", label="自动识别密码"),
                ft.Radio(value="custom", label="使用自定义密码"),
            ],
            spacing=18,
        ),
    )

    custom_password_input = ft.TextField(
        label="自定义密码",
        hint_text="输入要用于已选文件的密码",
        password=True,
        can_reveal_password=True,
        visible=False,
        border_radius=12,
    )

    password_hint_text = ft.Text(
        "自动模式：从文件名中提取 xxblXXXXXXXX 作为密码",
        size=11,
        color=TEXT_SOFT,
    )

    def on_password_mode_change(e=None):
        use_custom = password_mode.value == "custom"
        custom_password_input.visible = use_custom
        if use_custom:
            password_hint_text.value = "自定义模式：对当前选中的所有文件统一使用你输入的密码"
        else:
            password_hint_text.value = "自动模式：从文件名中提取 xxblXXXXXXXX 作为密码"
        safe_update()

    password_mode.on_change = on_password_mode_change

    password_section = ft.Container(
        width=380,
        bgcolor=PANEL,
        border_radius=18,
        border=ft.Border.all(1, BORDER),
        padding=16,
        content=ft.Column(
            [
                ft.Text("密码设置", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                password_mode,
                custom_password_input,
                password_hint_text,
            ],
            spacing=10,
        ),
    )

    # =========================================================
    # 15. 手动浏览逻辑
    # =========================================================
    def toggle_manual_file(path: str):
        if path in manual_selected_paths:
            manual_selected_paths.remove(path)
        else:
            manual_selected_paths.add(path)

        refresh_manual_picked_list()
        load_directory(current_browse_path)
        update_extract_btn_state()

    def load_directory(path: str):
        nonlocal current_browse_path
        current_browse_path = path
        current_path_text.value = path
        save_last_browse_path(path)
        explorer_list_view.controls.clear()

        try:
            items = os.listdir(path)
            dirs = []
            files = []

            for item in items:
                if item.startswith("."):
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    dirs.append(item)
                else:
                    files.append(item)

            dirs.sort(key=str.lower)
            files.sort(key=str.lower)

            parent_dir = os.path.dirname(path)
            if parent_dir and parent_dir != path:
                explorer_list_view.controls.append(
                    make_click_card(
                        title="返回上一级",
                        icon_name=ft.Icons.ARROW_UPWARD,
                        on_click=lambda e, p=parent_dir: load_directory(p),
                        bgcolor=PANEL_2,
                        icon_color=PRIMARY_LIGHT,
                        subtitle=parent_dir,
                    )
                )

            for d in dirs:
                d_path = os.path.join(path, d)
                explorer_list_view.controls.append(
                    make_click_card(
                        title=d,
                        icon_name=ft.Icons.FOLDER_ROUNDED,
                        on_click=lambda e, p=d_path: load_directory(p),
                        bgcolor=PANEL_2,
                        icon_color=FOLDER,
                        subtitle=d_path,
                    )
                )

            for f in files:
                f_path = os.path.join(path, f)
                is_target = f.lower().endswith((".zip", ".xls"))
                is_selected = f_path in manual_selected_paths

                bg_color = PRIMARY if is_selected else PANEL_2
                icon_color = PRIMARY_LIGHT if is_target else TEXT_SOFT
                text_color = "#FFFFFF" if is_selected else (TEXT if is_target else TEXT_SOFT)
                sub = "可选择解压文件" if is_target else "非目标文件"

                explorer_list_view.controls.append(
                    make_click_card(
                        title=f,
                        icon_name=ft.Icons.INSERT_DRIVE_FILE_ROUNDED,
                        on_click=(lambda e, p=f_path: toggle_manual_file(p)) if is_target else None,
                        bgcolor=bg_color,
                        icon_color=icon_color,
                        text_color=text_color,
                        subtitle=sub,
                    )
                )

            if not dirs and not files:
                explorer_list_view.controls.append(
                    ft.Container(
                        padding=12,
                        content=ft.Text("这个文件夹是空的", color=TEXT_SOFT),
                    )
                )

        except Exception:
            explorer_list_view.controls.append(
                ft.Container(
                    padding=12,
                    content=ft.Text("无法访问这个目录（可能需要授予权限）", color=DANGER),
                )
            )

        safe_update()

    # =========================================================
    # 16. 扫描逻辑
    # =========================================================
    def update_extract_btn_state():
        current_selected = get_current_selected_count()
        extract_btn.disabled = current_selected == 0

        if current_tab == "scan":
            if current_selected == 0:
                set_status("请在扫描结果中选择文件")
            else:
                set_status(f"已选择 {current_selected} 个扫描文件", PRIMARY_LIGHT)
        else:
            if current_selected == 0:
                set_status("请在手动浏览中选择文件")
            else:
                set_status(f"已选择 {current_selected} 个手动文件", PRIMARY_LIGHT)

        update_stat_cards()

    def toggle_scan_file(path: str, control: ft.Control):
        if path in selected_file_paths:
            selected_file_paths.remove(path)
            control.bgcolor = PANEL_2
        else:
            selected_file_paths.add(path)
            control.bgcolor = PRIMARY
        update_extract_btn_state()

    async def toggle_select_all(e=None):
        cards = [
            ctrl
            for ctrl in file_list_view.controls
            if isinstance(ctrl, ft.Container) and getattr(ctrl, "data", None)
        ]
        if not cards:
            return

        if len(selected_file_paths) == len(cards):
            selected_file_paths.clear()
            for card in cards:
                card.bgcolor = PANEL_2
        else:
            for card in cards:
                if card.data:
                    selected_file_paths.add(card.data)
                    card.bgcolor = PRIMARY

        update_extract_btn_state()

    async def scan_files(e=None):
        nonlocal last_scan_count
        file_list_view.controls.clear()
        selected_file_paths.clear()

        def get_scan_dirs():
            dirs = []

            if page.platform == ft.PagePlatform.ANDROID:
                candidates = [
                    "/storage/emulated/0/Download",
                    "/storage/emulated/0/Tencent/QQfile_recv",
                    "/storage/emulated/0/Android/data/com.tencent.mobileqq/Tencent/QQfile_recv",
                ]
            else:
                home = os.path.expanduser("~")
                candidates = [
                    os.path.join(home, "Downloads"),
                    os.path.join(home, "Desktop"),
                ]

            for path in candidates:
                if os.path.exists(path) and os.path.isdir(path):
                    dirs.append(path)

            return dirs

        scan_dirs = get_scan_dirs()
        found_files = []
        seen_paths = set()

        for scan_dir in scan_dirs:
            try:
                for root, dirs, files in os.walk(scan_dir):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for f in files:
                        lower = f.lower()

                        if (
                            ("xxbl" in lower)
                            or lower.endswith(".xls")
                            or lower.endswith(".zip")
                        ) and not f.startswith("."):
                            full_path = os.path.join(root, f)

                            if os.path.isfile(full_path) and full_path not in seen_paths:
                                seen_paths.add(full_path)
                                try:
                                    mtime = os.path.getmtime(full_path)
                                except Exception:
                                    mtime = 0
                                found_files.append((f, full_path, mtime))
            except Exception:
                pass

        found_files.sort(key=lambda x: x[2], reverse=True)
        last_scan_count = len(found_files)

        if not found_files:
            file_list_view.controls.append(
                ft.Container(
                    padding=12,
                    content=ft.Text(
                        "没有找到可解压文件\n请点击上方红色按钮授予全盘扫描权限\n或检查文件是否已保存到 Download 文件夹",
                        color=TEXT_SOFT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                )
            )
            select_all_btn.disabled = True
            set_status("扫描完成，没有找到目标文件", WARNING)
        else:
            select_all_btn.disabled = False

            for fname, fpath, _ in found_files:
                card = make_click_card(
                    title=fname,
                    icon_name=ft.Icons.DESCRIPTION_ROUNDED,
                    on_click=None,
                    bgcolor=PANEL_2,
                    icon_color=PRIMARY_LIGHT,
                    subtitle=fpath,
                    data=fpath,
                )
                card.on_click = lambda e, p=fpath, c=card: toggle_scan_file(p, c)
                file_list_view.controls.append(card)

            set_status(
                f"扫描完成，已找到 {len(found_files)} 个伪装包文件",
                SUCCESS,
            )

        update_extract_btn_state()

    # =========================================================
    # 17. 解压逻辑
    # =========================================================
    async def start_extraction(e=None):
        nonlocal extracted_item_count
        active_paths = get_active_paths()
        if not active_paths:
            return

        use_custom_password = password_mode.value == "custom"
        custom_password = custom_password_input.value.strip()

        if use_custom_password and not custom_password:
            set_status("你已选择自定义密码模式，请先输入密码", DANGER)
            return

        extract_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0
        safe_update()

        total_files = len(active_paths)
        total_extracted_items = 0
        password_error_count = 0
        other_error_count = 0
        error_messages = []
        successful_paths.clear()

        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        def extract_logic(file_path: str, pwd: str) -> int:
            with zipfile.ZipFile(file_path, "r") as zf:
                extract_count = 0

                for file_info in zf.infolist():
                    if file_info.is_dir():
                        continue

                    dest_path = os.path.join(output_dir, file_info.filename)
                    parent = os.path.dirname(dest_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)

                    base, ext = os.path.splitext(dest_path)
                    final_dest = dest_path
                    counter = 1
                    while os.path.exists(final_dest):
                        final_dest = f"{base}_{counter}{ext}"
                        counter += 1

                    with zf.open(file_info, pwd=pwd.encode("utf-8")) as source, open(final_dest, "wb") as target:
                        shutil.copyfileobj(source, target)

                    extract_count += 1

            return extract_count

        for idx, current_file_path in enumerate(active_paths, start=1):
            filename = os.path.basename(current_file_path)
            progress_bar.value = (idx - 1) / total_files
            set_status(f"正在处理 ({idx}/{total_files})：{filename}", PRIMARY_LIGHT)
            safe_update()

            try:
                if use_custom_password:
                    current_pwd = custom_password
                else:
                    pwd_match = re.search(r"(xxbl\d{8})", filename, flags=re.IGNORECASE)
                    if not pwd_match:
                        raise Exception("未找到密码")
                    current_pwd = pwd_match.group(1)

                count = await asyncio.to_thread(extract_logic, current_file_path, current_pwd)
                total_extracted_items += count
                successful_paths.add(current_file_path)

            except Exception as ex:
                raw_msg = str(ex)
                lower_msg = raw_msg.lower()

                is_password_error = (
                    "bad password" in lower_msg
                    or "wrong password" in lower_msg
                    or "password" in lower_msg
                    or "bad crc-32" in lower_msg
                    or "decrypt" in lower_msg
                    or "encrypted" in lower_msg
                )

                if raw_msg == "未找到密码":
                    final_msg = "未找到密码"
                    other_error_count += 1
                elif is_password_error:
                    final_msg = "密码错误"
                    password_error_count += 1
                else:
                    final_msg = raw_msg
                    other_error_count += 1

                error_messages.append(f"{filename}: {final_msg}")

        progress_bar.value = 1
        extract_btn.disabled = False
        extracted_item_count = total_extracted_items
        update_stat_cards()

        total_error_count = len(error_messages)
        if total_error_count > 0:
            if password_error_count > 0:
                set_status(
                    f"完成，但有 {total_error_count} 个文件解压失败（其中密码错误 {password_error_count} 个）",
                    WARNING,
                )
            else:
                set_status(f"完成，但有 {total_error_count} 个文件解压失败", WARNING)
        else:
            set_status(f"全部成功，共解压 {total_extracted_items} 个文件", SUCCESS)

        safe_update()

        if successful_paths:
            delete_dialog.open = True
            safe_update()

    # =========================================================
    # 18. 选项卡
    # =========================================================
    def switch_tab(e):
        nonlocal current_tab
        tab_name = e.control.data

        if tab_name == "scan":
            current_tab = "scan"
            scan_view.visible = True
            manual_view.visible = False
            tab_scan_btn.bgcolor = PRIMARY
            tab_manual_btn.bgcolor = PANEL
        else:
            current_tab = "manual"
            scan_view.visible = False
            manual_view.visible = True
            tab_scan_btn.bgcolor = PANEL
            tab_manual_btn.bgcolor = PRIMARY
            load_directory(current_browse_path)

        update_extract_btn_state()

    tab_scan_btn = ft.Container(
        data="scan",
        on_click=switch_tab,
        bgcolor=PRIMARY,
        border_radius=14,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        expand=True,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH, size=18, color=ft.Colors.WHITE),
                ft.Text("智能扫描", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
    )

    tab_manual_btn = ft.Container(
        data="manual",
        on_click=switch_tab,
        bgcolor=PANEL,
        border_radius=14,
        border=ft.Border.all(1, BORDER),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        expand=True,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.FOLDER_OPEN, size=18, color=ft.Colors.WHITE),
                ft.Text("手动浏览", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
    )

    tab_section = ft.Container(
        width=380,
        content=ft.Row(
            [tab_scan_btn, tab_manual_btn],
            spacing=10,
        ),
    )

    # =========================================================
    # 19. 扫描区 UI
    # =========================================================
    rescan_btn = ft.Button("重新扫描", on_click=scan_files)
    select_all_btn = ft.Button("全选 / 取消", on_click=toggle_select_all)

    scan_toolbar = ft.Row(
        [rescan_btn, select_all_btn],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    scan_view = ft.Container(
        width=380,
        visible=True,
        bgcolor=PANEL,
        border_radius=18,
        border=ft.Border.all(1, BORDER),
        padding=16,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("扫描结果", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text("自动扫描 Download / QQfile_recv", size=12, color=TEXT_SOFT),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                scan_toolbar,
                ft.Container(
                    height=280,
                    bgcolor=BG,
                    border_radius=14,
                    border=ft.Border.all(1, BORDER),
                    padding=8,
                    content=file_list_view,
                ),
            ],
            spacing=12,
        ),
    )

    # =========================================================
    # 20. 手动浏览区 UI
    # =========================================================
    home_btn = ft.Container(
        width=36,
        height=36,
        border_radius=10,
        bgcolor=PANEL_2,
        border=ft.Border.all(1, BORDER),
        alignment=ft.Alignment(0, 0),
        on_click=lambda e: load_directory(get_root_dir()),
        content=ft.Icon(ft.Icons.HOME_ROUNDED, size=18, color=PRIMARY_LIGHT),
    )

    path_bar = ft.Container(
        expand=True,
        height=36,
        bgcolor=BG,
        border_radius=10,
        border=ft.Border.all(1, BORDER),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        content=current_path_text,
    )

    manual_view = ft.Container(
        width=380,
        visible=False,
        content=ft.Column(
            [
                ft.Container(
                    bgcolor=PANEL,
                    border_radius=18,
                    border=ft.Border.all(1, BORDER),
                    padding=16,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("手动浏览", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                                    ft.Text("支持记住上次目录", size=12, color=TEXT_SOFT),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Row(
                                [home_btn, path_bar],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(
                                height=240,
                                bgcolor=BG,
                                border_radius=14,
                                border=ft.Border.all(1, BORDER),
                                padding=8,
                                content=explorer_list_view,
                            ),
                        ],
                        spacing=12,
                    ),
                ),
                ft.Container(
                    bgcolor=PANEL,
                    border_radius=18,
                    border=ft.Border.all(1, BORDER),
                    padding=16,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("已选文件", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                                    ft.Text("点击右侧 × 可移除", size=12, color=TEXT_SOFT),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(
                                height=150,
                                bgcolor=BG,
                                border_radius=14,
                                border=ft.Border.all(1, BORDER),
                                padding=8,
                                content=selected_list_view,
                            ),
                        ],
                        spacing=12,
                    ),
                ),
            ],
            spacing=12,
        ),
    )

    # =========================================================
    # 21. 底部操作区
    # =========================================================
    extract_btn = ft.Button(
        "开始解压",
        on_click=start_extraction,
        disabled=True,
        width=380,
        height=52,
    )

    footer_tip = ft.Text(
        "自动模式会从文件名提取密码；自定义模式会统一使用你输入的密码",
        size=11,
        color=TEXT_SOFT,
        text_align=ft.TextAlign.CENTER,
    )

    action_section = ft.Container(
        width=380,
        bgcolor=PANEL,
        border_radius=18,
        border=ft.Border.all(1, BORDER),
        padding=16,
        content=ft.Column(
            [
                extract_btn,
                footer_tip,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # =========================================================
    # 22. 页面布局
    # =========================================================
    page.add(
        header_section,
        permission_btn,  # 这是我刚刚为你加进去的！安卓端必点的红色权限按钮
        stats_section,
        status_section,
        tab_section,
        password_section,
        scan_view,
        manual_view,
        action_section,
    )

    # =========================================================
    # 23. 初始化
    # =========================================================
    refresh_manual_picked_list()
    load_directory(current_browse_path)
    on_password_mode_change()
    update_stat_cards()
    await scan_files()


if __name__ == "__main__":
    ft.run(main)
