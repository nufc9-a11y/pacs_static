"""Local diagnostic and demo launcher; not yet a live statistics collector."""
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from demo import generate_demo
from windows_probe import discover_windows, save_report


def main():
    root = tk.Tk()
    root.title('PACS 통계 — 화면 진단 / 양식 확인')
    root.geometry('660x430')
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='PACS 화면 자동 수집 준비', font=('', 16, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='현재 버전은 화면 구조 진단과 가상 데이터 엑셀 출력입니다.\n실제 검사 수집·실시간 통계 기능은 아직 연결되지 않았습니다.',
              wraplength=610).pack(anchor='w', pady=12)
    ttk.Label(frame, text='AE Title 목록: ER_DR / ER_M / DR9 / DR10 / DR19').pack(anchor='w')
    status = tk.StringVar(value='PACS를 열고 검사 목록 화면을 표시한 뒤 화면 진단을 실행하세요.')
    windows = []
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

    buttons = ttk.Frame(frame)
    buttons.pack(fill='x', pady=12)
    ttk.Button(buttons, text='PACS 창 찾기', command=refresh).pack(side='left', padx=4)
    ttk.Button(buttons, text='화면 구조 진단', command=diagnose).pack(side='left', padx=4)
    ttk.Button(buttons, text='가상 통계 엑셀 만들기', command=demo).pack(side='left', padx=4)
    ttk.Label(frame, textvariable=status, wraplength=610).pack(anchor='w', pady=12)
    root.mainloop()


if __name__ == '__main__':
    main()
