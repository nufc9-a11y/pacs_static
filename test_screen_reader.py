import unittest
from datetime import date
from screen_reader import parse_rows, ScreenReadError

HEADERS = ['ID', 'Name', 'Study date', 'Modality', 'Series count',
           'Instance count', 'Source AETitle', 'Requesting name']


class ScreenReaderTests(unittest.TestCase):
    def test_today_aetitle_and_ai(self):
        rows = [
            ['ignored', 'ignored', '2026-10-07 01:59:00', 'DX\\PR', '2', '3', 'ER_DR', 'Chest PA and LateralLeft'],
            ['ignored', 'ignored', '2026-10-07 02:00:00', 'DX', '1', '2', 'DR9', 'Abdomen Supine, Erect'],
            ['ignored', 'ignored', '2026-10-06 23:59:00', 'DX', '1', '1', 'ER_DR', 'Chest AP'],
        ]
        result = parse_rows(HEADERS, rows, ['ER_DR', 'DR9'], date(2026, 10, 7))
        self.assertEqual(result['ER_DR'], {0: [1, 3, 1, 0, 0]})
        self.assertEqual(result['DR9'], {1: [1, 2, 0, 0, 0]})

    def test_truncated_headers_fail(self):
        with self.assertRaises(ScreenReadError):
            parse_rows(['Study date', 'Insta...'], [], ['ER_DR'], date(2026, 10, 7))

    def test_misaligned_rows_fail(self):
        with self.assertRaises(ScreenReadError):
            parse_rows(HEADERS, [['too few']], ['ER_DR'], date(2026, 10, 7))

    def test_invalid_counts_fail(self):
        rows = [['ignored', 'ignored', '2026-10-07 01:59:00', 'DX\\PR', '2', 'O', 'ER_DR', 'Chest AP']]
        with self.assertRaises(ScreenReadError):
            parse_rows(HEADERS, rows, ['ER_DR'], date(2026, 10, 7))


if __name__ == '__main__':
    unittest.main()
