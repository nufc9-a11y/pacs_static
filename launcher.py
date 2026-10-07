"""Local UIA snapshot preview, diagnostics and demo; not a complete collector."""
from datetime import datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from demo import generate_demo
from windows_probe import discover_windows, save_report
from screen_reader import ScreenReadError, parse_rows, read_snapshot
from pacs_statistics import KOREA
from scroll_collector import ScanCancelled, UIAScrollDriver, collect


def main():
    root = tk.Tk()
    root.title('PACS 통계 — 화면 진단 / 양식 확인')
    root.geometry('760x680')
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='PACS 화면 자동 수집 준비', font=('', 16, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='오늘 검사 목록 읽기 미리보기와 화면 진단을 제공합니다.\n목록 전체 수집이 미확인 상태이므로 미리보기를 확정 통계로 저장하지 않습니다.',
              wraplength=610).pack(anchor='w', pady=12)
    ttk.Label(frame, text='AE Title 선택 또는 입력 (여러 개는 쉼표로 구분)').pack(anchor='w')
    ae_entry = ttk.Combobox(frame, values=['ER_DR', 'ER_M', 'DR9', 'DR10', 'DR19', 'ER_DR,ER_M'])
    ae_entry.set('ER_DR')
    ae_entry.pack(fill='x', pady=4)
    status = tk.StringVar(value='PACS를 열고 검사 목록 화면을 표시한 뒤 화면 진단을 실행하세요.')
    windows = []
    events = queue.Queue()
    stop = threading.Event()
    scanning = False
    selection = ttk.Combobox(frame, state='readonly', width=65)
    selection.pack(fill='x', pady=12)

    def refresh():
        try:
            windows[:] = discover_windows()
            selection['values'] = [f'PACS 창 {i + 1} — 창 핸들 {w.handle}' for i, w in enumerate(windows)]
            if windows:
                selection.current(0)
            status.set(f'PACS 후보 창 {len(windows)}개. 진단 대상 창을 선택하세요.')
        except Exception:
            status.set('화면 진단을 시작하지 못했습니다. Windows와 의존성 설치를 확인하세요.')

    def diagnose():
        index = selection.current()
        if index < 0 or index >= len(windows):
            messagebox.showinfo('창 선택', '먼저 PACS 창 찾기를 실행하세요.')
            return
        target = filedialog.asksaveasfilename(defaultextension='.json',
                                             initialfile='pacs_ui_report.json',
                                             filetypes=[('진단 보고서', '*.json')])
        if not target:
            return
        try:
            result = save_report(windows[index], target)
            status.set(f"진단 저장 완료: 표 요소 {result['table_control_count']}개, 알려진 열 {len(result['recognized_headers'])}개.\n검사 데이터는 수집하지 않았습니다.")
        except Exception:
            messagebox.showerror('진단 실패', 'PACS 화면을 읽지 못했습니다. 실행 권한과 PACS 창 상태를 확인하세요.')

    def demo():
        folder = filedialog.askdirectory(title='가상 통계 파일 저장 폴더')
        if not folder:
            return
        target = Path(folder) / ('PACS_DEMO_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        try:
            paths = generate_demo(target)
            status.set(f'가상 통계 {len(paths)}개 저장: {target}\n모두 2026-10-07 가상 데이터이며 실제 병원 통계가 아닙니다.')
        except Exception:
            messagebox.showerror('출력 실패', '샘플 출력에 실패했습니다. 저장 폴더 접근과 템플릿을 확인하세요.')

    def show_groups(grouped):
        for item in results.get_children():
            results.delete(item)
        for title, buckets in grouped.items():
            for slot in range(12):
                exam, images, s2, s3, s4 = buckets.get(slot, [0, 0, 0, 0, 0])
                results.insert('', 'end', values=(title, f'{slot*2:02d}~{slot*2+2:02d}',
                                                   exam, images - s2 - 2*s3 - 3*s4))

    def preview():
        index = selection.current()
        if index < 0 or index >= len(windows):
            messagebox.showinfo('창 선택', '먼저 PACS 창 찾기를 실행하세요.')
            return
        titles = list(dict.fromkeys(t.strip() for t in ae_entry.get().split(',') if t.strip()))
        if not titles:
            messagebox.showinfo('검사실 선택', 'AE Title을 선택하거나 입력하세요.')
            return
        for item in results.get_children():
            results.delete(item)
        now = datetime.now(KOREA)
        try:
            headers, rows = read_snapshot(windows[index])
            grouped = parse_rows(headers, rows, titles, now.date())
            show_groups(grouped)
            status.set(f'{now:%Y-%m-%d %H:%M:%S} 한국 시간 기준 / 읽은 행 {len(rows)}개.\n부분 목록 미리보기입니다. 전체 검사 수·누락·중복은 미검증입니다.')
        except ScreenReadError as exc:
            messagebox.showerror('화면 읽기 확인 필요', str(exc))
        except Exception:
            messagebox.showerror('화면 읽기 실패', '예상하지 못한 화면 구조입니다. 화면 진단을 실행하세요.')

    def start_scan():
        nonlocal scanning
        if scanning:
            return
        index = selection.current()
        titles = list(dict.fromkeys(t.strip() for t in ae_entry.get().split(',') if t.strip()))
        if index < 0 or index >= len(windows) or not titles:
            messagebox.showinfo('선택 필요', 'PACS 창과 AE Title을 선택하세요.')
            return
        handle = windows[index].handle
        day = datetime.now(KOREA).date()
        stop.clear()
        scanning = True
        for button in action_buttons:
            button.configure(state='disabled')
        selection.configure(state='disabled')
        ae_entry.configure(state='disabled')
        show_groups({})
        status.set('목록 맨 위부터 자동 스크롤을 시작합니다. 수집 중 PACS 목록을 변경하지 마세요.')

        def worker():
            initialized = False
            try:
                import comtypes
                comtypes.CoInitialize()
                initialized = True
                from pywinauto import Desktop
                window = Desktop(backend='uia').window(handle=handle).wrapper_object()
                driver = UIAScrollDriver(window)
                headers, rows = collect(driver, stop,
                                        lambda count, pct: events.put(('progress', (count, pct))))
                if stop.is_set():
                    raise ScanCancelled('수집을 중지했습니다.')
                grouped = parse_rows(headers, rows, titles, day)
                events.put(('done', (grouped, len(rows), day)))
            except ScreenReadError as exc:
                events.put(('error', str(exc)))
            except Exception:
                events.put(('error', '스크롤 수집에 실패했습니다. 화면 구조와 실행 권한을 확인하세요.'))
            finally:
                if initialized:
                    comtypes.CoUninitialize()

        threading.Thread(target=worker, daemon=True).start()

    def poll_events():
        nonlocal scanning
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == 'progress':
                    count, pct = payload
                    status.set(f'자동 스크롤 {pct:.1f}% / 반복 행을 제외한 행 {count}개. 중지 버튼으로 취소할 수 있습니다.')
                    continue
                scanning = False
                for button in action_buttons:
                    button.configure(state='normal')
                selection.configure(state='readonly')
                ae_entry.configure(state='normal')
                if kind == 'done':
                    if stop.is_set():
                        status.set('수집을 중지했습니다. 확정 통계는 저장하지 않았습니다.')
                        continue
                    grouped, count, day = payload
                    show_groups(grouped)
                    status.set(f'{day} 기준 / 목록 스크롤 끝까지 읽음: {count}개 행.\n검색 조건·다른 페이지·검사 식별자는 미검증입니다. 확정 통계가 아닌 미리보기입니다.')
                else:
                    status.set(payload)
        except queue.Empty:
            pass
        root.after(100, poll_events)

    buttons = ttk.Frame(frame)
    buttons.pack(fill='x', pady=12)
    action_buttons = []
    for label, command in [('PACS 창 찾기', refresh), ('화면 구조 진단', diagnose), ('가상 통계 엑셀 만들기', demo)]:
        button = ttk.Button(buttons, text=label, command=command)
        button.pack(side='left', padx=4)
        action_buttons.append(button)
    scans = ttk.Frame(frame)
    scans.pack(fill='x', pady=4)
    for label, command in [('현재 목록 읽기', preview), ('오늘 검사 자동 스크롤 미리보기', start_scan)]:
        button = ttk.Button(scans, text=label, command=command)
        button.pack(side='left', padx=4)
        action_buttons.append(button)
    ttk.Button(scans, text='중지', command=stop.set).pack(side='left', padx=4)
    results = ttk.Treeview(frame, columns=('ae', 'time', 'exam', 'image'), show='headings', height=10)
    for key, label in [('ae', 'AE Title'), ('time', '시간대'), ('exam', 'exam'), ('image', 'AI 제외 image')]:
        results.heading(key, text=label)
        results.column(key, width=140)
    results.pack(fill='both', expand=True, pady=8)
    ttk.Label(frame, textvariable=status, wraplength=610).pack(anchor='w', pady=12)
    root.protocol('WM_DELETE_WINDOW', lambda: (stop.set(), root.destroy()))
    root.after(100, poll_events)
    root.mainloop()


if __name__ == '__main__':
    main()
