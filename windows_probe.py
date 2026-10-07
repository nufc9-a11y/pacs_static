"""Read-only UI Automation probe. Never writes patient names or screen images."""
import json
import platform
from collections import Counter
from pathlib import Path

HEADERS = {'Study date', 'Modality', 'Series count', 'Instance count',
           'Source AETitle', 'Source AE Title', 'Requesting name', 'Exam status'}


def discover_windows():
    if platform.system() != 'Windows':
        raise RuntimeError('PACS 화면 진단은 병원 Windows PC에서 실행해야 합니다.')
    from pywinauto import Desktop
    # Titles are used only locally for selecting PACS, never written to a report.
    return [w for w in Desktop(backend='uia').windows()
            if 'pacs' in w.window_text().lower() or 'infinitt' in w.window_text().lower()]


def probe(window):
    try:
        controls = window.descendants()
        types = Counter(c.element_info.control_type for c in controls)
        # Only known non-patient column labels are retained.
        found = set()
        for control in controls:
            if control.element_info.control_type in ('HeaderItem', 'Text'):
                label = control.window_text().strip()
                if label in HEADERS:
                    found.add(label)
        return dict(report_version=1, method='Windows UI Automation',
                    control_type_counts=dict(types), recognized_headers=sorted(found),
                    table_control_count=types['Table'] + types['DataGrid'],
                    data_item_count=types['DataItem'],
                    complete_collection_verified=False,
                    note='제어 요소와 열 제목만 진단했습니다. 검사 데이터 수집은 수행하지 않았습니다.')
    except Exception:
        # Avoid serializing exceptions that may contain patient-bearing UI text.
        raise RuntimeError('화면 구조를 읽지 못했습니다. PACS와 프로그램의 실행 권한을 확인하세요.') from None


def save_report(window, destination):
    result = probe(window)
    Path(destination).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
