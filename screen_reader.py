"""Strict, read-only reader for UIA tables. A snapshot never proves completeness."""
from datetime import datetime
import re

from pacs_statistics import KOREA, aggregate


class ScreenReadError(ValueError):
    pass


def header_key(label):
    aliases = {
        'studydate': 'study_datetime', 'modality': 'modality',
        'seriescount': 'series_count', 'instancecount': 'instance_count',
        'sourceaetitle': 'source_aetitle', 'requestingname': 'description',
    }
    return aliases.get(re.sub(r'[^a-z]', '', label.lower()))


REQUIRED = {'study_datetime', 'modality', 'series_count', 'instance_count',
            'source_aetitle', 'description'}


def parse_rows(headers, rows, titles, day):
    keys = [header_key(h) for h in headers]
    if not REQUIRED <= set(keys):
        raise ScreenReadError('필수 열을 읽지 못했습니다. 날짜·Modality·Series/Instance count·AE Title·검사명을 모두 표시하세요.')
    if any(keys.count(key) != 1 for key in REQUIRED):
        raise ScreenReadError('열 구분이 중복되어 화면 구조 확인이 필요합니다.')
    records = []
    for index, cells in enumerate(rows):
        if len(cells) != len(headers):
            raise ScreenReadError('열과 행의 칸 수가 다릅니다. 화면 구조 진단이 필요합니다.')
        raw = {key: value.strip() for key, value in zip(keys, cells) if key}
        try:
            timestamp = datetime.fromisoformat(raw['study_datetime'])
            if timestamp.tzinfo:
                timestamp = timestamp.astimezone(KOREA)
        except ValueError:
            raise ScreenReadError('검사 날짜·시간을 해석하지 못했습니다.') from None
        if timestamp.date() != day or raw['source_aetitle'] not in titles:
            continue
        for field in ('series_count', 'instance_count'):
            if not re.fullmatch(r'[0-9]+', raw[field]):
                raise ScreenReadError('Series/Instance count가 숫자로 읽히지 않았습니다.')
            raw[field] = int(raw[field])
        raw['study_datetime'] = timestamp.isoformat()
        raw['is_chest'] = bool(re.search(r'\bchest\b', raw.pop('description'), flags=re.I))
        # Snapshot-only row key. This must never be used to deduplicate scrolling.
        raw['study_id'] = f'SNAPSHOT-{index}'
        records.append(raw)
    result = {}
    for title in titles:
        try:
            result[title] = dict(aggregate(records, day, title))
        except ValueError:
            raise ScreenReadError('AI 차감 또는 장수에 확인이 필요한 값이 있습니다.') from None
    return result


def read_snapshot(window):
    """Only accept unambiguous tables with direct DataItem/cell structure."""
    candidates = []
    try:
        for table in window.descendants():
            if table.element_info.control_type not in ('Table', 'DataGrid', 'List'):
                continue
            header_controls = [c for c in table.descendants()
                               if c.element_info.control_type == 'HeaderItem']
            header_controls.sort(key=lambda c: c.rectangle().left)
            headers = [c.window_text().strip() for c in header_controls]
            if not REQUIRED <= {header_key(h) for h in headers}:
                continue
            rows = []
            for item in table.children():
                if item.element_info.control_type not in ('DataItem', 'ListItem'):
                    continue
                cells = [c for c in item.children()
                         if c.element_info.control_type in ('Text', 'Custom', 'Edit')]
                cells.sort(key=lambda c: c.rectangle().left)
                if len(cells) != len(headers):
                    raise ScreenReadError('PACS 행 구조를 아직 지원하지 않습니다. 화면 진단 보고서가 필요합니다.')
                rows.append([c.window_text() for c in cells])
            if rows:
                candidates.append((headers, rows))
    except ScreenReadError:
        raise
    except Exception:
        raise ScreenReadError('PACS 표 읽기에 실패했습니다. 창 상태와 실행 권한을 확인하세요.') from None
    if len(candidates) != 1:
        raise ScreenReadError('검사 목록을 하나로 식별하지 못했습니다. 화면 구조 진단이 필요합니다.')
    return candidates[0]
