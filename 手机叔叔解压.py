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
    page.title = "全自动解压器"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 380
    page.window.height = 760
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 24

    # 状态变量
    selected_file_paths = set()
    successful_paths = set()

    # ==========================================
    # 2. 权限与路径逻辑
    # ==========================================
    def get_download_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/Download"
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def get_output_dir() -> str:
        if page.platform == ft.PagePlatform.ANDROID:
            return "/storage/emulated/0/QQ解压的视频文件"
        return os.path.join(os.path.expanduser("~"), "Desktop", "QQ解压的视频文件")

    async def check_permissions():
        """申请安卓所有文件访问权限"""
        if page.platform == ft.PagePlatform.ANDROID:
            status = await page.get_permission_status(ft.PermissionType.MANAGE_EXTERNAL_STORAGE)
            if status != ft.PermissionStatus.GRANTED:
                status = await page.request_permission(ft.PermissionType.MANAGE_EXTERNAL_STORAGE)
            
            if status == ft.PermissionStatus.GRANTED:
                status_text.value = "✅ 已获得存储访问权限"
                status_text.color = ft.Colors.GREEN_400
                await scan_files()
            else:
                status_text.value = "❌ 权限被拒绝，请在设置中手动开启"
                status_text.color = ft.Colors.RED_400
            page.update()

    # ==========================================
    # 3. UI 组件与弹窗
    # ==========================================
    title = ft.Text("📦 智能全自动解压", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    subtitle = ft.Text("正在深度扫描 Download 及子文件夹...", size=12, color=ft.Colors.GREY_500)

    file_list_view = ft.ListView(expand=True, spacing=10, height=260)
    status_text = ft.Text("正在检查权限...", size=14, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER)
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
            except:
                pass
        status_text.value = f"🗑️ 已清理 {success_count} 个源文件"
        status_text.color = ft.Colors.GREEN_400
        delete_dialog.open = False
        page.update()
        page.run_task(scan_files)

    delete_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("🎉 解压成功"),
        content=ft.Text("文件已保存至【QQ解压的视频文件】。\n\n是否删除原始压缩包以释放空间？"),
        actions=[
            ft.Button("保留", on_click=close_dlg),
            ft.Button("删除", on_click=delete_source_file, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
        ],
    )
    page.overlay.append(delete_dialog)

    # ==========================================
    # 4. 核心功能逻辑
    # ==========================================
    async def select_file(path, btn_control):
        if path in selected_file_paths:
            selected_file_paths.remove(path)
            btn_control.style.bgcolor = ft.Colors.BLUE_GREY_800
        else:
            selected_file_paths.add(path)
            btn_control.style.bgcolor = ft.Colors.BLUE_600
        
        extract_btn.disabled = len(selected_file_paths) == 0
        status_text.value = f"已选中 {len(selected_file_paths)} 个文件"
        page.update()

    async def toggle_select_all(e):
        all_btns = [c for c in file_list_view.controls if isinstance(c, ft.Button)]
        if not all_btns: return
        
        if len(selected_file_paths) == len(all_btns):
            selected_file_paths.clear()
            for btn in all_btns: btn.style.bgcolor = ft.Colors.BLUE_GREY_800
        else:
            for btn in all_btns:
                selected_file_paths.add(btn.data)
                btn.style.bgcolor = ft.Colors.BLUE_600
        
        extract_btn.disabled = len(selected_file_paths) == 0
        status_text.value = f"已选中 {len(selected_file_paths)} 个文件"
        page.update()

    async def scan_files(e=None):
        file_list_view.controls.clear()
        selected_file_paths.clear()
        download_dir = get_download_dir()
        found_files = []

        if os.path.exists(download_dir):
            for root, _, files in os.walk(download_dir):
                for f in files:
                    # 匹配伪装包规则
                    if ("xxbl" in f.lower() or f.endswith(".xls") or f.endswith(".zip")) and not f.startswith("."):
                        full_path = os.path.join(root, f)
                        found_files.append((f, full_path, os.path.getmtime(full_path)))

        found_files.sort(key=lambda x: x[2], reverse=True)

        if not found_files:
            file_list_view.controls.append(ft.Text("😭 未找到可用文件", color=ft.Colors.RED_300))
            extract_btn.disabled = True
            select_all_btn.disabled = True
        else:
            select_all_btn.disabled = False
            for fname, fpath, _ in found_files:
                btn = ft.Button(
                    content=ft.Text(f"📄 {fname}", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    data=fpath, width=320, height=45,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_800, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8), alignment=ft.Alignment(-1, 0))
                )
                btn.on_click = lambda e, p=fpath, c=btn: page.run_task(select_file, p, c)
                file_list_view.controls.append(btn)
            status_text.value = f"发现 {len(found_files)} 个文件"
        page.update()

    async def start_extraction(e):
        extract_btn.disabled = True
        progress_bar.visible = True
        successful_paths.clear()
        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        total = len(selected_file_paths)
        for i, path in enumerate(list(selected_file_paths), 1):
            fname = os.path.basename(path)
            status_text.value = f"解压中 ({i}/{total}): {fname}"
            progress_bar.value = i / total
            page.update()

            try:
                pwd_match = re.search(r'(xxbl\d{8})', fname)
                pwd = pwd_match.group(1) if pwd_match else ""
                
                def run_zip():
                    count = 0
                    with pyzipper.AESZipFile(path, 'r') as zf:
                        if pwd: zf.setpassword(pwd.encode())
                        for info in zf.infolist():
                            if info.is_dir(): continue
                            target = os.path.join(output_dir, info.filename)
                            os.makedirs(os.path.dirname(target), exist_ok=True)
                            with zf.open(info.filename) as s, open(target, 'wb') as t:
                                shutil.copyfileobj(s, t)
                            count += 1
                    return count

                await asyncio.to_thread(run_zip)
                successful_paths.add(path)
            except Exception as ex:
                print(f"Error: {ex}")

        progress_bar.visible = False
        status_text.value = "🎉 处理完成！"
        if successful_paths: delete_dialog.open = True
        extract_btn.disabled = False
        page.update()

    # ==========================================
    # 5. 组装 UI
    # ==========================================
    rescan_btn = ft.IconButton(icon=ft.Icons.REFRESH, on_click=scan_files, icon_color=ft.Colors.BLUE_300)
    select_all_btn = ft.TextButton("全选/取消", on_click=toggle_select_all, disabled=True)
    extract_btn = ft.ElevatedButton("开始解压", on_click=start_extraction, disabled=True, width=320, height=50)

    page.add(
        ft.Container(height=10), title, subtitle,
        ft.Row([rescan_btn, select_all_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Container(content=file_list_view, border=ft.Border.all(1, ft.Colors.BLUE_GREY_700), border_radius=10, padding=10),
        ft.Container(height=15), extract_btn, ft.Container(height=10), progress_bar, status_text,
    )

    await check_permissions()

if __name__ == "__main__":
    ft.app(target=main)
