"""Bounded, read-only inventory. No filenames, patient data or tag values in reports."""
from collections import Counter
from pathlib import Path
import io
import os

FIELDS = ['StudyDate', 'StudyTime', 'Modality', 'StudyInstanceUID',
          'SeriesInstanceUID', 'SOPInstanceUID', 'StudyDescription', 'BodyPartExamined']
KNOWN_EXTENSIONS = {'.dcm', '.dicom', '.db', '.sqlite', '.sqlite3', '.mdb', '.mdf', '.ldf',
                    '.exe', '.dll', '.ini', '.xml', '.json', '.log', '.txt', '.dat', '.bin',
                    '.jpg', '.jpeg', '.png', '.bmp', '.zip', '.cab', '.config', '.csv', '.xlsx'}


def inspect_folder(folder, stop, max_files=10000, max_samples=100):
    root = Path(folder)
    if not root.is_dir() or root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
        raise ValueError('일반 로컬 폴더를 선택하세요. 폴더가 없거나 연결 경로입니다.')
    extensions, fields = Counter(), Counter()
    files = signatures = samples = failures = links = unrecognized = 0
    truncated = cancelled = False
    pending = [root]
    while pending:
        if stop.is_set():
            cancelled = True
            break
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if stop.is_set():
                        cancelled = True
                        break
                    path = Path(entry.path)
                    if entry.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                        links += 1
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    if files >= max_files:
                        truncated = True
                        break
                    files += 1
                    ext = path.suffix.lower()
                    extensions[ext if ext in KNOWN_EXTENSIONS else '(other/no extension)'] += 1
                    try:
                        with path.open('rb') as stream:
                            prefix = stream.read(132)
                            if prefix[128:132] != b'DICM':
                                if ext in ('.dcm', '.dicom'):
                                    unrecognized += 1
                                continue
                            signatures += 1
                            if samples >= max_samples:
                                continue
                            samples += 1
                            # Cap metadata reading; do not load pixel data or entire files.
                            data = prefix + stream.read(2 * 1024 * 1024 - 132)
                        import pydicom
                        dataset = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True,
                                                 specific_tags=FIELDS)
                        for field in FIELDS:
                            if field in dataset and dataset.get(field) not in (None, ''):
                                fields[field] += 1
                        if dataset.file_meta.get('SourceApplicationEntityTitle'):
                            fields['SourceApplicationEntityTitle'] += 1
                    except Exception:
                        failures += 1
                if cancelled or truncated:
                    break
        except OSError:
            failures += 1
    return dict(report_version=1, method='read-only folder inventory',
                files_inspected=files, extension_counts=dict(extensions),
                dicom_part10_signatures=signatures, dicom_samples_attempted=samples,
                non_part10_dicom_extension_files=unrecognized,
                metadata_field_presence_counts=dict(fields), unreadable_or_parse_errors=failures,
                skipped_links=links, file_limit_reached=truncated, cancelled=cancelled,
                traversal_complete=not (truncated or cancelled or failures or links),
                metadata_sampling_limited=signatures > samples,
                complete_today_dataset_verified=False,
                note='파일명·경로·환자 정보·DICOM 값·영상은 보고서에 포함하지 않았습니다. SourceApplicationEntityTitle이 PACS 목록의 Source AE Title과 같은지는 미확인입니다.')


def open_folder_probe(root):
    import json
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    dialog = tk.Toplevel(root)
    dialog.title('PACS 저장 폴더 점검')
    dialog.geometry('650x470')
    ttk.Label(dialog, text='파일 종류와 DICOM 항목의 존재 여부만 점검합니다.\n폴더와 파일을 수정하지 않으며 실제 검사 전체 저장 여부는 별도 확인이 필요합니다.',
              padding=12).pack(fill='x')
    folder = tk.StringVar(value=r'C:\INFINITT')
    ttk.Entry(dialog, textvariable=folder).pack(fill='x', padx=12)
    ttk.Button(dialog, text='폴더 선택', command=lambda: choose()).pack(pady=4)
    status = tk.StringVar(value='기본 제한: 파일 10,000개, DICOM 메타데이터 샘플 100개')
    ttk.Label(dialog, textvariable=status, wraplength=610, padding=12).pack(fill='x')
    text = tk.Text(dialog, height=10, wrap='word')
    text.pack(fill='both', expand=True, padx=12)
    events, stop = queue.Queue(), threading.Event()
    saved_report = []

    def choose():
        selected = filedialog.askdirectory(initialdir=folder.get())
        if selected:
            folder.set(selected)

    def scan():
        path = folder.get()
        saved_report.clear()
        save_button.configure(state='disabled')
        scan_button.configure(state='disabled')
        stop.clear()
        status.set('읽기 전용으로 점검 중…')
        def worker():
            try:
                events.put(inspect_folder(path, stop))
            except Exception:
                events.put(None)
        threading.Thread(target=worker, daemon=True).start()

    def save():
        target = filedialog.asksaveasfilename(initialfile='pacs_folder_report.json', defaultextension='.json')
        if target:
            try:
                Path(target).write_text(json.dumps(saved_report[0], ensure_ascii=False, indent=2), encoding='utf-8')
                status.set('진단 보고서를 저장했습니다. 파일명·환자 정보·영상은 포함하지 않습니다.')
            except OSError:
                messagebox.showerror('저장 실패', '보고서를 저장하지 못했습니다.')

    scan_button = ttk.Button(dialog, text='폴더 점검 시작', command=scan)
    scan_button.pack(pady=4)
    ttk.Button(dialog, text='중지', command=stop.set).pack()
    save_button = ttk.Button(dialog, text='진단 JSON 저장', command=save, state='disabled')
    save_button.pack(pady=4)

    def poll():
        if not dialog.winfo_exists():
            return
        try:
            report = events.get_nowait()
            scan_button.configure(state='normal')
            text.delete('1.0', 'end')
            if report is None:
                status.set('폴더를 점검하지 못했습니다. 경로와 읽기 권한을 확인하세요.')
            else:
                saved_report.append(report)
                text.insert('end', json.dumps(report, ensure_ascii=False, indent=2))
                save_button.configure(state='normal')
                status.set('점검 완료. 중지·제한·읽기 오류 여부는 보고서에 표시됩니다. 오늘 검사 전체성은 미확인입니다.')
        except queue.Empty:
            pass
        dialog.after(100, poll)
    dialog.protocol('WM_DELETE_WINDOW', lambda: (stop.set(), dialog.destroy()))
    dialog.after(100, poll)
