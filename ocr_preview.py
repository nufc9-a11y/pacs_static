"""Local Windows OCR preview using the operating system OCR engine."""
import base64
import io
import json
import platform
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import queue


def recognize(image):
    if platform.system() != 'Windows':
        raise RuntimeError('Windows 10/11 PC에서 실행하세요.')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    payload = json.dumps({'png': base64.b64encode(buffer.getvalue()).decode('ascii')})
    script = Path(__file__).resolve().parent / 'windows_ocr.ps1'
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)],
                            input=payload, capture_output=True, encoding='utf-8',
                            timeout=40, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        data = json.loads(result.stdout.lstrip('\ufeff').strip())
    except (ValueError, TypeError):
        raise RuntimeError('Windows OCR을 실행하지 못했습니다. PowerShell 실행 정책과 Windows 버전을 확인하세요.') from None
    if result.returncode or not data.get('ok'):
        if data.get('error') == 'OCR_LANGUAGE_MISSING':
            raise RuntimeError('Windows 영어(en-US) OCR 언어 기능이 필요합니다. Windows 언어 설정을 확인하세요.')
        raise RuntimeError('Windows OCR 인식에 실패했습니다. 선택 영역 크기와 Windows OCR 기능을 확인하세요.')
    return data


def select_region(root, callback, on_cancel=None):
    """Select a primary-monitor rectangle; screenshot remains in local memory."""
    from PIL import ImageGrab
    root.withdraw()
    overlay = tk.Toplevel(root)
    overlay.attributes('-fullscreen', True)
    overlay.attributes('-topmost', True)
    overlay.attributes('-alpha', 0.3)
    canvas = tk.Canvas(overlay, bg='black', cursor='crosshair', highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    canvas.create_text(20, 20, anchor='nw', fill='white',
                       text='검사 목록 영역을 드래그하세요. 환자 이름·번호 영역은 제외하세요. ESC: 취소')
    origin = []
    box = []

    def restore():
        overlay.destroy()
        root.deiconify()

    def start(event):
        origin[:] = [event.x_root, event.y_root]
        if box:
            canvas.delete(box.pop())
        box.append(canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='yellow', width=2))

    def move(event):
        if origin and box:
            canvas.coords(box[0], origin[0], origin[1], event.x, event.y)

    def finish(event):
        if not origin:
            return
        bounds = (min(origin[0], event.x_root), min(origin[1], event.y_root),
                  max(origin[0], event.x_root), max(origin[1], event.y_root))
        overlay.withdraw()

        def capture():
            try:
                if bounds[2] - bounds[0] < 20 or bounds[3] - bounds[1] < 20:
                    raise RuntimeError('읽을 영역을 조금 더 크게 지정하세요.')
                image = ImageGrab.grab(bbox=bounds)
                restore()
                callback(image)
            except Exception as exc:
                if overlay.winfo_exists():
                    restore()
                messagebox.showerror('영역 선택 실패', str(exc))
        root.after(350, capture)

    canvas.bind('<ButtonPress-1>', start)
    canvas.bind('<B1-Motion>', move)
    canvas.bind('<ButtonRelease-1>', finish)
    def cancel(event):
        restore()
        if on_cancel:
            on_cancel()
    overlay.bind('<Escape>', cancel)
    overlay.focus_force()


def open_preview(root):
    dialog = tk.Toplevel(root)
    dialog.title('PACS OCR — 인식 결과 확인')
    dialog.geometry('780x560')
    ttk.Label(dialog, padding=12, wraplength=740,
              text='PACS를 주 모니터에 표시한 뒤 목록 영역을 지정하세요. 날짜·Modality·Series/Instance count·AE Title·검사명이 보이게 선택합니다.\n화면과 결과는 이 PC에서만 처리하며 파일 저장이나 외부 전송을 하지 않습니다. OCR 결과는 통계로 자동 확정하지 않습니다.').pack(fill='x')
    text = tk.Text(dialog, wrap='none', height=18)
    text.pack(fill='both', expand=True, padx=12)
    status = tk.StringVar(value='인식된 숫자와 열 제목을 PACS 화면과 비교해 주세요.')
    ttk.Label(dialog, textvariable=status, padding=12, wraplength=740).pack(fill='x')
    events = queue.Queue()

    def received(image):
        button.configure(state='disabled')
        status.set('Windows OCR로 인식 중…')
        def worker():
            try:
                events.put((True, recognize(image)))
            except Exception as exc:
                events.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def choose():
        dialog.withdraw()
        def done(image):
            dialog.deiconify()
            received(image)
        select_region(root, done, dialog.deiconify)

    button = ttk.Button(dialog, text='목록 영역 지정하고 OCR 읽기', command=choose)
    button.pack(pady=8)

    def poll():
        if not dialog.winfo_exists():
            return
        try:
            success, value = events.get_nowait()
            button.configure(state='normal')
            text.delete('1.0', 'end')
            if success:
                for line in value['lines']:
                    text.insert('end', line['text'] + '\n')
                status.set(f"인식된 줄 {len(value['lines'])}개. 원본과 대조가 필요합니다. 전체 수집·장수 정확성은 미검증입니다.")
            else:
                status.set(value)
        except queue.Empty:
            pass
        dialog.after(100, poll)
    dialog.after(100, poll)
