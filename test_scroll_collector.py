import threading
import unittest

from scroll_collector import ScanCancelled, collect
from screen_reader import ScreenReadError


class Driver:
    def __init__(self, pages):
        self.pages = pages
        self.index = 0

    def top(self):
        self.index = 0

    def snapshot(self, stop):
        return self.pages[self.index]

    def advance(self):
        self.index = min(self.index + 1, len(self.pages) - 1)


class ScrollTests(unittest.TestCase):
    def test_overlapping_rows(self):
        driver = Driver([(['col'], [['a'], ['b']], 0), (['col'], [['b'], ['c']], 50),
                         (['col'], [['c'], ['d']], 100)])
        progress = []
        headers, rows = collect(driver, threading.Event(), lambda n, p: progress.append((n, p)))
        self.assertEqual(rows, [['a'], ['b'], ['c'], ['d']])
        self.assertEqual(progress[-1], (4, 100))

    def test_stuck_scroll_fails(self):
        with self.assertRaises(ScreenReadError):
            collect(Driver([(['col'], [['a']], 0)]), threading.Event(), lambda *args: None)

    def test_changed_columns_fail(self):
        with self.assertRaises(ScreenReadError):
            collect(Driver([(['col'], [['a']], 0), (['new'], [['b']], 100)]),
                    threading.Event(), lambda *args: None)

    def test_cancel(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(ScanCancelled):
            collect(Driver([]), stop, lambda *args: None)

    def test_indistinguishable_rows_fail(self):
        with self.assertRaises(ScreenReadError):
            collect(Driver([(['col'], [['a'], ['a']], 100)]), threading.Event(), lambda *args: None)


if __name__ == '__main__':
    unittest.main()
