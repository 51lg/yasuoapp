import asyncio
import os
import re
import shutil
import zipfile
from pathlib import Path

import flet as ft
import flet_permission_handler as fph


APP_TITLE = "全自动解压器（权限弹窗版）"


async def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 20
    page.window.width = 390
    page.window.height = 780

    permission_handler = fph.PermissionHandler()
    page.services.append(permission_handler)

    selected_file_paths: set[str] = set()
    successful_paths: set[str] = set()
    all_found_files: list[tuple[str, str, float]] = []

    def is_android() -> bool:
        return page.platform == ft.PagePlatform.ANDROID

    def get_scan_dirs() -> list[str]:
        if is_android():
            return [
                "/storage/emulated/0/QQfile_recv",
                "/storage/emulated/0/Download",
            ]
        home = str(Path.home())
        return [
            os.path.join(home, "Downloads"),
            os.path.join(home, "Desktop"),
        ]

    def get_output_dir() -> str:
        if is_android():
            return "/storage/emulated/0/QQ解压的视频文件"
        return os.path.join(str(Path.home()), "Desktop", "QQ解压的视频文件")

    def normalize_path(p: str) -> str:
        return os.path.normpath(p)

    def supported_file(filename: str) -> bool:
        name = filename.lower()
        return (
            "xxbl" in name or name.endswith(".xls") or name.endswith(".zip")
        ) and not filename.startswith(".")

    title = ft.Text(
        "📦 智能全自动解压",
        size=24,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.BLUE_300,
    )
    subtitle = ft.Text(
        "启动后会扫描 QQfile_recv + Download",
        size=12,
        color=ft.Colors.GREY_400,
    )

    permission_hint = ft.Text(
        "权限状态：待检查",
        size=13,
        color=ft.Colors.AMBER_300,
        text_align=ft.TextAlign.CENTER,
    )
    status_text = ft.Text(
        "等待操作...",
        size=14,
        color=ft.Colors.GREY_300,
        text_align=ft.TextAlign.CENTER,
    )
    progress_bar = ft.ProgressBar(width=320, value=0, visible=False)
    file_list_view = ft.ListView(expand=True, spacing=8, height=300)

    async def show_snack(text: str):
        page.open(ft.SnackBar(content=ft.Text(text)))
        page.update()

    async def open_settings_dialog(_: ft.ControlEvent | None = None):
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("需要存储权限"),
            content=ft.Text(
                "当前没有足够权限读取 QQfile_recv / Download。\n\n"
                "点击“去设置开启”后，在系统页面里允许文件访问权限，然后再回到 App 点“重新扫描”。"
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dialog(dialog)),
                ft.TextButton("去设置开启", on_click=lambda e: page.run_task(open_settings_and_close, dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dialog)
        page.update()

    def close_dialog(dialog: ft.AlertDialog):
        dialog.open = False
        page.update()

    async def open_settings_and_close(dialog: ft.AlertDialog):
        dialog.open = False
        page.update()
        await permission_handler.open_app_settings()

    async def refresh_permission_hint():
        if not is_android():
            permission_hint.value = "当前为桌面环境：无需安卓存储权限"
            permission_hint.color = ft.Colors.GREEN_300
            page.update()
            return True

        manage_status = await permission_handler.get_status(
            fph.Permission.MANAGE_EXTERNAL_STORAGE
        )
        storage_status = await permission_handler.get_status(fph.Permission.STORAGE)

        manage_ok = manage_status and manage_status.name.lower() == "granted"
        storage_ok = storage_status and storage_status.name.lower() == "granted"

        if manage_ok:
            permission_hint.value = "权限状态：已获得全部文件访问权限"
            permission_hint.color = ft.Colors.GREEN_300
            page.update()
            return True

        if storage_ok:
            permission_hint.value = "权限状态：已获得基础存储权限（部分机型可用）"
            permission_hint.color = ft.Colors.LIGHT_GREEN_300
            page.update()
            return True

        permission_hint.value = "权限状态：未授权，可能无法读取手机文件"
        permission_hint.color = ft.Colors.RED_300
        page.update()
        return False

    async def request_storage_permissions(_: ft.ControlEvent | None = None):
        if not is_android():
            await show_snack("桌面端无需申请安卓权限")
            return

        status_text.value = "正在申请文件读取权限..."
        status_text.color = ft.Colors.WHITE
        page.update()

        manage_status = await permission_handler.request(
            fph.Permission.MANAGE_EXTERNAL_STORAGE
        )
        manage_ok = manage_status and manage_status.name.lower() == "granted"

        if manage_ok:
            await refresh_permission_hint()
            status_text.value = "✅ 已获取全部文件访问权限"
            status_text.color = ft.Colors.GREEN_300
            page.update()
            await scan_files()
            return

        storage_status = await permission_handler.request(fph.Permission.STORAGE)
        storage_ok = storage_status and storage_status.name.lower() == "granted"

        await refresh_permission_hint()

        if storage_ok:
            status_text.value = "✅ 已获取基础存储权限，开始重新扫描"
            status_text.color = ft.Colors.GREEN_300
            page.update()
            await scan_files()
            return

        status_text.value = "❌ 权限未授予，请到系统设置中手动开启"
        status_text.color = ft.Colors.RED_300
        page.update()
        await open_settings_dialog()

    def set_button_selected(btn: ft.Button, selected: bool):
        btn.style = ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_600 if selected else ft.Colors.BLUE_GREY_800,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
            alignment=ft.Alignment(-1, 0),
        )

    async def select_file(path: str, btn_control: ft.Button):
        path = normalize_path(path)
        if path in selected_file_paths:
            selected_file_paths.remove(path)
            set_button_selected(btn_control, False)
        else:
            selected_file_paths.add(path)
            set_button_selected(btn_control, True)

        extract_btn.disabled = len(selected_file_paths) == 0
        status_text.value = (
            f"已选中 {len(selected_file_paths)} 个文件，随时可以开始解压！"
            if selected_file_paths
            else "请选择要解压的文件"
        )
        status_text.color = ft.Colors.WHITE
        page.update()

    async def toggle_select_all(_: ft.ControlEvent):
        btns = [c for c in file_list_view.controls if isinstance(c, ft.Button)]
        if not btns:
            return

        if len(selected_file_paths) == len(btns):
            selected_file_paths.clear()
            for btn in btns:
                set_button_selected(btn, False)
        else:
            selected_file_paths.clear()
            for btn in btns:
                selected_file_paths.add(normalize_path(str(btn.data)))
                set_button_selected(btn, True)

        extract_btn.disabled = len(selected_file_paths) == 0
        status_text.value = (
            f"已选中 {len(selected_file_paths)} 个文件，随时可以开始解压！"
            if selected_file_paths
            else "请选择要解压的文件"
        )
        page.update()

    async def scan_files(_: ft.ControlEvent | None = None):
        file_list_view.controls.clear()
        selected_file_paths.clear()
        all_found_files.clear()
        extract_btn.disabled = True
        select_all_btn.disabled = True

        dirs = get_scan_dirs()
        subtitle.value = "正在扫描 QQfile_recv + Download 及其子文件夹..."
        status_text.value = "正在扫描文件..."
        status_text.color = ft.Colors.WHITE
        page.update()

        has_permission = await refresh_permission_hint()
        if is_android() and not has_permission:
            file_list_view.controls.append(
                ft.Text(
                    "⚠️ 当前没有存储权限，请先点上方“申请权限”",
                    color=ft.Colors.ORANGE_300,
                    text_align=ft.TextAlign.CENTER,
                )
            )
            status_text.value = "请先授予权限，再重新扫描"
            status_text.color = ft.Colors.ORANGE_300
            page.update()
            return

        dedup: dict[str, tuple[str, str, float]] = {}
        for scan_dir in dirs:
            if not os.path.exists(scan_dir):
                continue
            for root, _, files in os.walk(scan_dir):
                for name in files:
                    if not supported_file(name):
                        continue
                    full_path = normalize_path(os.path.join(root, name))
                    if not os.path.isfile(full_path):
                        continue
                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        continue
                    dedup[full_path] = (name, full_path, mtime)

        all_found_files.extend(sorted(dedup.values(), key=lambda x: x[2], reverse=True))

        if not all_found_files:
            file_list_view.controls.append(
                ft.Text(
                    "😭 未找到任何可解压文件\n请确认文件已保存到 QQfile_recv 或 Download",
                    color=ft.Colors.RED_300,
                    text_align=ft.TextAlign.CENTER,
                )
            )
            status_text.value = "未发现可用文件"
            status_text.color = ft.Colors.RED_300
            page.update()
            return

        select_all_btn.disabled = False
        for fname, fpath, _ in all_found_files:
            btn = ft.Button(
                content=f"📄 {fname}",
                data=fpath,
                width=330,
                height=48,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE_GREY_800,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    alignment=ft.Alignment(-1, 0),
                ),
            )
            btn.on_click = lambda e, p=fpath, c=btn: page.run_task(select_file, p, c)
            file_list_view.controls.append(btn)

        subtitle.value = "扫描完成：已覆盖 QQfile_recv + Download"
        status_text.value = f"扫描完成，共找到 {len(all_found_files)} 个文件"
        status_text.color = ft.Colors.GREEN_300
        page.update()

    def extract_one_archive(file_path: str, password: str, output_dir: str) -> int:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                extracted = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue

                    dest_path = os.path.join(output_dir, info.filename)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                    base, ext = os.path.splitext(dest_path)
                    final_dest = dest_path
                    index = 1
                    while os.path.exists(final_dest):
                        final_dest = f"{base}_{index}{ext}"
                        index += 1

                    parent_dir = os.path.dirname(final_dest)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)

                    with zf.open(info, "r", pwd=password.encode("utf-8")) as source, open(final_dest, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted += 1
                return extracted
        except zipfile.BadZipFile as exc:
            raise ValueError("文件不是有效的 ZIP 压缩包，或扩展名伪装成 zip/xls/xxbl") from exc
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "password" in msg or "encrypted" in msg:
                raise ValueError("当前安卓版仅支持标准 ZIP 解压，不支持 AES 加密压缩包") from exc
            raise
        except NotImplementedError as exc:
            raise ValueError("当前压缩算法暂不受支持，可能是 AES 加密压缩包") from exc

    def parse_password(filename: str) -> str:
        match = re.search(r"(xxbl\d{8})", filename, re.IGNORECASE)
        if not match:
            raise ValueError("未找到密码（文件名需包含 xxbl8位数字）")
        return match.group(1)

    async def close_delete_dialog(_: ft.ControlEvent):
        delete_dialog.open = False
        page.update()

    async def delete_source_files(_: ft.ControlEvent):
        deleted = 0
        for path in list(successful_paths):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted += 1
            except OSError:
                pass

        delete_dialog.open = False
        status_text.value = f"🗑️ 已删除 {deleted} 个源文件"
        status_text.color = ft.Colors.GREEN_300
        page.update()
        await scan_files()

    delete_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("🎉 解压完成"),
        content=ft.Text(
            "文件已解压到【QQ解压的视频文件】目录。\n\n是否删除原始压缩包以释放手机空间？"
        ),
        actions=[
            ft.TextButton("保留文件", on_click=close_delete_dialog),
            ft.TextButton("删除源文件", on_click=delete_source_files),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    async def start_extraction(_: ft.ControlEvent):
        if not selected_file_paths:
            return

        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        extract_btn.disabled = True
        rescan_btn.disabled = True
        select_all_btn.disabled = True
        permission_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0
        successful_paths.clear()
        status_text.value = f"准备解压 {len(selected_file_paths)} 个文件..."
        status_text.color = ft.Colors.WHITE
        page.update()

        total = len(selected_file_paths)
        total_items = 0
        errors: list[str] = []

        for i, file_path in enumerate(list(selected_file_paths), start=1):
            filename = os.path.basename(file_path)
            status_text.value = f"正在解压 ({i}/{total})：{filename}"
            progress_bar.value = (i - 1) / total
            page.update()

            try:
                password = parse_password(filename)
                extracted_count = await asyncio.to_thread(
                    extract_one_archive, file_path, password, output_dir
                )
                total_items += extracted_count
                successful_paths.add(file_path)
            except Exception as ex:
                msg = str(ex)
                errors.append(f"{filename}: {msg}")

        progress_bar.value = 1
        if errors:
            brief = "\n".join(errors[:2])
            if len(errors) > 2:
                brief += "\n..."
            status_text.value = f"完成，但有 {len(errors)} 个错误：\n{brief}"
            status_text.color = ft.Colors.ORANGE_300
        else:
            status_text.value = f"🎉 全部成功！共解压 {total_items} 个内部文件"
            status_text.color = ft.Colors.GREEN_300

        extract_btn.disabled = False
        rescan_btn.disabled = False
        select_all_btn.disabled = False
        permission_btn.disabled = False
        page.update()

        if successful_paths:
            page.open(delete_dialog)
            page.update()

    permission_btn = ft.Button(
        content="🔐 申请权限",
        on_click=request_storage_permissions,
        style=ft.ButtonStyle(color=ft.Colors.AMBER_300),
    )
    rescan_btn = ft.Button(
        content="🔄 重新扫描",
        on_click=scan_files,
        style=ft.ButtonStyle(color=ft.Colors.BLUE_300),
    )
    select_all_btn = ft.Button(
        content="☑️ 全选 / 取消",
        on_click=toggle_select_all,
        disabled=True,
        style=ft.ButtonStyle(color=ft.Colors.BLUE_300),
    )
    extract_btn = ft.Button(
        content="开始解压",
        on_click=start_extraction,
        disabled=True,
        width=330,
        height=54,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
    )

    page.add(
        ft.Container(height=10),
        title,
        subtitle,
        permission_hint,
        ft.Row(
            [permission_btn, rescan_btn, select_all_btn],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Container(
            content=file_list_view,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_700),
            border_radius=12,
            padding=10,
        ),
        ft.Container(height=12),
        extract_btn,
        ft.Container(height=8),
        progress_bar,
        status_text,
        ft.Container(height=8),
        ft.Text(
            "输出目录：QQ解压的视频文件",
            size=12,
            color=ft.Colors.GREY_500,
            text_align=ft.TextAlign.CENTER,
        ),
    )

    await refresh_permission_hint()
    await request_storage_permissions()


if __name__ == "__main__":
    ft.run(main)
