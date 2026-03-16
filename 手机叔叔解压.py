import flet as ft
import pyzipper
import os
import re
import shutil
import asyncio


async def main(page: ft.Page):
    page.title = "全自动解压器（安卓省事版）"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 380
    page.window.height = 760
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 24
    page.scroll = ft.ScrollMode.AUTO

    selected_file_path = ""

    def get_input_path(filename: str) -> str:
        name = filename.strip().strip('"').strip("'")
        if not name:
            return ""
        if os.path.isabs(name):
            return name
        if page.platform == "android":
            return os.path.join("/storage/emulated/0/Download", name)
        return os.path.join(os.path.expanduser("~"), "Downloads", name)

    def get_output_dir() -> str:
        if page.platform == "android":
            return "/storage/emulated/0/Download/解压视频"
        return os.path.join(os.path.expanduser("~"), "Desktop", "解压视频")

    title = ft.Text(
        "📦 全自动解压器",
        size=24,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.BLUE_400,
    )
    subtitle = ft.Text(
        "安卓省事版：只输入文件名即可",
        size=12,
        color=ft.Colors.GREY_500,
    )
    tips = ft.Text(
        "默认从 Download 目录读取文件。\n"
        "例如你只需要输入：xxbl20260315.xls\n"
        "也支持直接粘贴完整路径。",
        size=12,
        color=ft.Colors.GREY_400,
        text_align=ft.TextAlign.CENTER,
    )

    filename_input = ft.TextField(
        label="请输入文件名",
        hint_text="例如：xxbl20260315.xls",
        width=320,
        multiline=False,
        text_size=14,
        border_radius=10,
    )

    resolved_path_text = ft.Text(
        "",
        size=12,
        color=ft.Colors.BLUE_GREY_200,
        text_align=ft.TextAlign.CENTER,
        selectable=True,
    )
    status_text = ft.Text(
        "等待输入文件名...",
        size=14,
        color=ft.Colors.GREY_400,
        text_align=ft.TextAlign.CENTER,
    )
    progress_bar = ft.ProgressBar(
        width=300,
        value=0,
        visible=False,
        color=ft.Colors.GREEN_400,
    )

    async def confirm_path(e):
        nonlocal selected_file_path
        raw_name = filename_input.value or ""
        full_path = get_input_path(raw_name)

        if not raw_name.strip():
            selected_file_path = ""
            extract_btn.disabled = True
            resolved_path_text.value = ""
            status_text.value = "请先输入文件名"
            status_text.color = ft.Colors.ORANGE_300
            page.update()
            return

        resolved_path_text.value = f"实际路径：{full_path}"

        if not os.path.exists(full_path):
            selected_file_path = ""
            extract_btn.disabled = True
            status_text.value = "文件不存在，请检查文件名是否在 Download 目录中"
            status_text.color = ft.Colors.RED_400
            page.update()
            return

        if not os.path.isfile(full_path):
            selected_file_path = ""
            extract_btn.disabled = True
            status_text.value = "目标不是文件，请重新输入"
            status_text.color = ft.Colors.RED_400
            page.update()
            return

        selected_file_path = full_path
        extract_btn.disabled = False
        status_text.value = "已找到文件，可以开始解压"
        status_text.color = ft.Colors.WHITE
        page.update()

    async def start_extraction(e):
        nonlocal selected_file_path
        if not selected_file_path:
            status_text.value = "请先确认文件名"
            status_text.color = ft.Colors.ORANGE_300
            page.update()
            return

        extract_btn.disabled = True
        confirm_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = None
        status_text.value = "正在处理..."
        status_text.color = ft.Colors.WHITE
        page.update()

        filename = os.path.basename(selected_file_path)

        try:
            pwd_match = re.search(r'(xxbl\d{8})', filename)
            if not pwd_match:
                raise Exception("未嗅探到密码结构（文件名需包含如 xxbl20260315）")
            current_pwd = pwd_match.group(1)

            status_text.value = f"已嗅探到密码：{current_pwd}\n正在解压中..."
            page.update()

            output_dir = get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            def do_extract():
                with pyzipper.AESZipFile(selected_file_path, 'r') as zf:
                    zf.setpassword(current_pwd.encode('utf-8'))
                    infolist = zf.infolist()
                    if not infolist:
                        raise Exception("压缩包为空")

                    extracted_files = []
                    for file_info in infolist:
                        if file_info.is_dir():
                            continue

                        dest_path = os.path.join(output_dir, file_info.filename)
                        parent_dir = os.path.dirname(dest_path)
                        if parent_dir:
                            os.makedirs(parent_dir, exist_ok=True)

                        base, ext = os.path.splitext(dest_path)
                        counter = 1
                        final_dest = dest_path
                        while os.path.exists(final_dest):
                            final_dest = f"{base}_{counter}{ext}"
                            counter += 1

                        with zf.open(file_info.filename, 'r') as source, open(final_dest, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        extracted_files.append(final_dest)

                return output_dir, extracted_files

            output_dir, extracted_files = await asyncio.to_thread(do_extract)

            status_text.value = (
                f"🎉 解压完成！\n"
                f"共解压 {len(extracted_files)} 个文件\n"
                f"保存位置：{output_dir}"
            )
            status_text.color = ft.Colors.GREEN_400
            progress_bar.value = 1

        except Exception as ex:
            error_msg = str(ex)
            if 'Bad password' in error_msg:
                error_msg = "密码错误或压缩格式不支持"
            status_text.value = f"⚠️ 错误：{error_msg}"
            status_text.color = ft.Colors.RED_400
            progress_bar.visible = False

        finally:
            extract_btn.disabled = False
            confirm_btn.disabled = False
            page.update()

    confirm_btn = ft.Button(
        "确认文件名",
        on_click=confirm_path,
        width=320,
        height=50,
    )

    extract_btn = ft.Button(
        "开始解压",
        on_click=start_extraction,
        disabled=True,
        width=320,
        height=55,
    )

    page.add(
        ft.Container(height=12),
        title,
        subtitle,
        ft.Container(height=24),
        tips,
        ft.Container(height=18),
        filename_input,
        ft.Container(height=12),
        confirm_btn,
        ft.Container(height=10),
        resolved_path_text,
        ft.Container(height=18),
        extract_btn,
        ft.Container(height=24),
        progress_bar,
        status_text,
    )

    page.update()


if __name__ == "__main__":
    ft.run(main)
