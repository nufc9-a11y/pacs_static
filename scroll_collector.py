"""Scrollable-list preview. End of scrolling does not prove complete PACS search."""
import hashlib
import json

from screen_reader import ScreenReadError, read_snapshot


class ScanCancelled(ScreenReadError):
    pass


def collect(driver, stop, progress, max_steps=2000):
    """Testable driver contract: top(), snapshot()->headers/rows/percent, advance()."""
    if stop.is_set():
        raise ScanCancelled('수집을 중지했습니다.')
    driver.top()
    seen = set()
    unique_rows = []
    expected_headers = None
    previous_position = -1
    for step in range(max_steps):
        if stop.is_set():
            raise ScanCancelled('수집을 중지했습니다. 확정 통계는 저장하지 않았습니다.')
        headers, rows, position = driver.snapshot(stop)
        if expected_headers is None:
            expected_headers = headers
        elif headers != expected_headers:
            raise ScreenReadError('수집 중 열 구성이 변경되어 중단했습니다.')
        if not 0 <= position <= 100 or position < previous_position:
            raise ScreenReadError('스크롤 위치가 변경되었거나 읽히지 않아 중단했습니다.')
        if step == 0 and position > 0.01:
            raise ScreenReadError('목록 맨 위로 이동하지 못했습니다.')
        if step and position <= previous_position:
            raise ScreenReadError('스크롤이 진행되지 않아 중단했습니다.')
        local_seen = set()
        for row in rows:
            if len(row) != len(headers):
                raise ScreenReadError('수집 중 열과 행의 칸 수가 달라졌습니다.')
            # Hash is session-local and is never written to files or logs.
            key = hashlib.sha256(json.dumps(row, ensure_ascii=False).encode()).digest()
            if key in local_seen:
                raise ScreenReadError('같은 화면에 구분할 수 없는 행이 있어 중단했습니다.')
            local_seen.add(key)
            if key not in seen:
                seen.add(key)
                unique_rows.append(row)
        progress(len(unique_rows), position)
        if position >= 99.99:
            return expected_headers, unique_rows
        previous_position = position
        driver.advance()
    raise ScreenReadError('스크롤 횟수 제한에 도달했습니다. 전체 수집으로 처리하지 않습니다.')


class UIAScrollDriver:
    def __init__(self, window):
        self.window = window
        _, _, self.table = read_snapshot(window, with_table=True)
        try:
            self.scroll = self.table.iface_scroll
            if not self.scroll.CurrentVerticallyScrollable:
                raise ScreenReadError('스크롤 가능한 표가 아닙니다. 단일 화면 미리보기를 사용하세요.')
        except ScreenReadError:
            raise
        except Exception:
            raise ScreenReadError('PACS 표가 자동 스크롤 기능을 제공하지 않습니다. 화면 진단이 필요합니다.') from None

    def top(self):
        try:
            self.scroll.SetScrollPercent(-1.0, 0.0)
        except Exception:
            raise ScreenReadError('목록 맨 위로 이동하지 못했습니다.') from None
        self.last_rows = None

    def advance(self):
        try:
            # UI Automation ScrollAmount: NoAmount=2, SmallIncrement=4.
            self.scroll.Scroll(2, 4)
        except Exception:
            raise ScreenReadError('PACS 목록 스크롤에 실패했습니다.') from None

    def snapshot(self, stop):
        previous = None
        for _ in range(20):
            if stop.wait(0.15):
                raise ScanCancelled('수집을 중지했습니다.')
            headers, rows, table = read_snapshot(self.window, with_table=True)
            if table.handle != self.table.handle or table.element_info.runtime_id != self.table.element_info.runtime_id:
                raise ScreenReadError('수집 중 검사 목록이 바뀌었습니다.')
            position = float(self.scroll.CurrentVerticalScrollPercent)
            current = (headers, rows, position)
            # After scrolling, stale content must change before accepting it.
            if current == previous and rows != self.last_rows:
                self.last_rows = rows
                return current
            previous = current
        raise ScreenReadError('검사 목록의 새 행이 안정적으로 로딩되지 않아 중단했습니다.')
