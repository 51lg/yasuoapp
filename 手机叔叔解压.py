import flet as ft
import pyzipper
import os
import re
import shutil
import asyncio

async def main(page: ft.Page):
    # ==========================================
    # 1. 页面基础设置
    # ==========================================
    page.title = "全自动解压器（深度扫描版）"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 380
    page.window.height = 760
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 24
    page.scroll = ft.ScrollMode.AUTO # 防止列表太长导致 UI 崩溃

    # 状态变量 (支持多选)
    selected_file_paths = set()
    successful_paths = set()

    # ==========================================
    # 2. 安卓权限申请与路径
    # ==========================================
    # 引入 Flet 官方权限管理器
    ph = ft.PermissionHandler()
    page.overlay.append(ph)

    def request_perms(e):
        ph.request_permission(ft.PermissionType.MANAGE_EXTERNAL_STORAGE)
        ph.request_permission(ft.PermissionType.STORAGE)

    perm_btn = ft.Container(
        content=ft.Text("⚠️ 安卓手机必点：授予读取文件权限", color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
        bgcolor=ft.Colors.RED_500,
        padding=10,
        border_radius=8,
        on_click=request_perms,
        visible=page.platform == ft.PagePlatform.ANDROID # 仅在安卓端显示
    )

    def get_download_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/Download"
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def get_output_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/QQ解压的视频文件"
        return os.path.join(os.path.expanduser("~"), "Desktop", "QQ解压的视频文件")

    # ==========================================
    # 3. UI 组件与弹窗
    # ==========================================
    title = ft.Text("📦 智能全自动解压", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    subtitle = ft.Text("正在深度扫描 Download 及子文件夹...", size=12, color=ft.Colors.GREY_500)

    file_list_view = ft.ListView(expand=True, spacing=10, height=260)

    status_text = ft.Text("等待操作...", size=14, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER)
    progress_bar = ft.ProgressBar(width=300, value=0, visible=False, color=ft.Colors.GREEN_400)

    def close_dlg(e):
        delete_dialog.open = False
        page.update()

    def delete_source_file(e):
        success_count = 0
        for path in list(successful_paths):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    success_count += 1
            except Exception as ex:
                pass

        status_text.value = f"🗑️ 成功删除 {success_count} 个源文件，已释放空间！"
        status_text.color = ft.Colors.GREEN_400

        delete_dialog.open = False
        page.update()
        page.run_task(scan_files)

    delete_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("🎉 解压成功"),
        content=ft.Text("文件已成功解压到【QQ解压的视频文件】目录下。\n\n是否要删除原始的压缩包以释放手机空间？"),
        actions=[
            ft.Button(content=ft.Text("保留文件"), on_click=close_dlg),
            ft.Button(content=ft.Text("删除源文件"), on_click=delete_source_file, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(delete_dialog)

    # ==========================================
    # 4. 交互逻辑
    # ==========================================
    async def select_file(path, btn_control):
        if path in selected_file_paths:
            selected_file_paths.remove(path)
            btn_control.style = ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_GREY_800,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                alignment=ft.Alignment(-1, 0)
            )
        else:
            selected_file_paths.add(path)
            btn_control.style = ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                alignment=ft.Alignment(-1, 0)
            )

        extract_btn.disabled = len(selected_file_paths) == 0
        if selected_file_paths:
            status_text.value = f"已选中 {len(selected_file_paths)} 个文件，随时可以开始解压！"
        else:
            status_text.value = "请选择要解压的文件"

        status_text.color = ft.Colors.WHITE
        page.update()

    async def toggle_select_all(e):
        all_btn_controls = [ctrl for ctrl in file_list_view.controls if isinstance(ctrl, ft.Button)]
        if not all_btn_controls: return

        if len(selected_file_paths) == len(all_btn_controls):
            selected_file_paths.clear()
            for btn in all_btn_controls:
                btn.style.bgcolor = ft.Colors.BLUE_GREY_800
        else:
            for btn in all_btn_controls:
                selected_file_paths.add(btn.data)
                btn.style.bgcolor = ft.Colors.BLUE_600

        extract_btn.disabled = len(selected_file_paths) == 0
        if selected_file_paths:
            status_text.value = f"已选中 {len(selected_file_paths)} 个文件，随时可以开始解压！"
        else:
            status_text.value = "请选择要解压的文件"

        page.update()

    async def scan_files(e=None):
        file_list_view.controls.clear()
        selected_file_paths.clear()
        download_dir = get_download_dir()
        found_files = []

        if os.path.exists(download_dir):
            for root, dirs, files in os.walk(download_dir):
                for f in files:
                    if ("xxbl" in f.lower() or f.endswith(".xls") or f.endswith(".zip")) and not f.startswith("."):
                        full_path = os.path.join(root, f)
                        if os.path.isfile(full_path):
                            found_files.append((f, full_path, os.path.getmtime(full_path)))

        found_files.sort(key=lambda x: x[2], reverse=True)

        if not found_files:
            file_list_view.controls.append(
                ft.Text("😭 未找到任何 xls 伪装包\n请检查文件是否已下载",
                        color=ft.Colors.RED_300, text_align=ft.TextAlign.CENTER)
            )
            extract_btn.disabled = True
            select_all_btn.disabled = True
            status_text.value = "未发现可用文件"
        else:
            select_all_btn.disabled = False
            for fname, fpath, _ in found_files:
                btn = ft.Button(
                    content=ft.Text(f"📄 {fname}"),
                    data=fpath,
                    width=320,
                    height=45,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE_GREY_800,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        alignment=ft.Alignment(-1, 0)
                    )
                )
                btn.on_click = lambda e, p=fpath, c=btn: page.run_task(select_file, p, c)
                file_list_view.controls.append(btn)
            status_text.value = f"扫描完成，共找到 {len(found_files)} 个文件"

        page.update()

    async def start_extraction(e):
        if not selected_file_paths: return

        extract_btn.disabled = True
        rescan_btn.disabled = True
        select_all_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0
        status_text.value = f"准备解压 {len(selected_file_paths)} 个文件..."
        status_text.color = ft.Colors.WHITE
        page.update()

        total_files = len(selected_file_paths)
        current_idx = 0
        total_extracted_items = 0
        error_messages = []
        successful_paths.clear()

        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        for current_file_path in list(selected_file_paths):
            current_idx += 1
            filename = os.path.basename(current_file_path)
            status_text.value = f"正在解压 ({current_idx}/{total_files}): {filename}..."
            progress_bar.value = (current_idx - 1) / total_files
            page.update()

            try:
                pwd_match = re.search(r'(xxbl\d{8})', filename)
                if not pwd_match:
                    raise Exception("未找到密码（需包含 xxbl8位数字）")
                current_pwd = pwd_match.group(1)

                def extract_logic(file_path, pwd):
                    with pyzipper.AESZipFile(file_path, 'r') as zf:
                        zf.setpassword(pwd.encode('utf-8'))
                        infolist = zf.infolist()
                        extract_count = 0
                        for file_info in infolist:
                            if file_info.is_dir(): continue
                            dest_path = os.path.join(output_dir, file_info.filename)

                            base, ext = os.path.splitext(dest_path)
                            counter = 1
                            final_dest = dest_path
                            while os.path.exists(final_dest):
                                final_dest = f"{base}_{counter}{ext}"
                                counter += 1

                            with zf.open(file_info.filename, 'r') as source, open(final_dest, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            extract_count += 1
                    return extract_count

                count = await asyncio.to_thread(extract_logic, current_file_path, current_pwd)
                total_extracted_items += count
                successful_paths.add(current_file_path)

            except Exception as ex:
                msg = str(ex)
                if 'Bad password' in msg: msg = "密码解析正确但解密失败"
                error_messages.append(f"{filename}: {msg}")

        progress_bar.value = 1

        if error_messages:
            err_str = "\n".join(error_messages[:2])
            if len(error_messages) > 2: err_str += "..."
            status_text.value = f"完成，但有{len(error_messages)}个错误:\n{err_str}"
            status_text.color = ft.Colors.ORANGE_400
        else:
            status_text.value = f"🎉 全部成功！共解压 {total_extracted_items} 个内部文件！"
            status_text.color = ft.Colors.GREEN_400

        if successful_paths:
            delete_dialog.open = True

        extract_btn.disabled = False
        rescan_btn.disabled = False
        select_all_btn.disabled = False
        page.update()

    # ==========================================
    # 5. 组装布局
    # ==========================================
    rescan_btn = ft.Button(
        content=ft.Text("🔄 重新扫描"),
        on_click=scan_files,
        style=ft.ButtonStyle(color=ft.Colors.BLUE_300)
    )
    select_all_btn = ft.Button(
        content=ft.Text("☑️ 全选 / 取消"),
        on_click=toggle_select_all,
        disabled=True,
        style=ft.ButtonStyle(color=ft.Colors.BLUE_300)
    )

    toolbar_row = ft.Row(
        [rescan_btn, select_all_btn],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    extract_btn = ft.Button(
        content=ft.Text("开始解压", size=16, weight=ft.FontWeight.BOLD),
        on_click=start_extraction,
        disabled=True,
        width=320,
        height=55,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE)
    )

    page.add(
        ft.Container(height=10),
        title,
        subtitle,
        perm_btn, # 安卓权限按钮
        toolbar_row,
        ft.Container(
            content=file_list_view,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_700),
            border_radius=10,
            padding=10
        ),
        ft.Container(height=15),
        extract_btn,
        ft.Container(height=10),
        progress_bar,
        status_text,
    )

    await scan_files()


if __name__ == "__main__":
    ft.run(main)
