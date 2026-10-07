import tempfile
import unittest
from datetime import date
from pathlib import Path

import openpyxl

from pacs_statistics import aggregate, export_day

TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'statistics_blank.xlsx'


def record(identifier='a', time='2026-10-07T01:59:00', ae='ER_DR', series=2, images=3):
    return dict(study_id=identifier, study_datetime=time, source_aetitle=ae,
                modality='DX\\PR', series_count=series, instance_count=images, is_chest=True)


class StatisticsTests(unittest.TestCase):
    def test_grouping_and_ai(self):
        records = [record(), record('b', '2026-10-07T02:00:00', series=3, images=4),
                   record('c', '2026-10-07T04:00:00', series=4, images=6),
                   record('d', ae='ER_M'), record('e', '2026-10-06T23:59:00')]
        b = aggregate(records, date(2026, 10, 7), 'ER_DR')
        self.assertEqual(b[0], [1, 3, 1, 0, 0])
        self.assertEqual(b[1], [1, 4, 0, 1, 0])
        self.assertEqual(b[2], [1, 6, 0, 0, 1])

    def test_reject_uncertain_records(self):
        for records in ([record(), record()], [record(series=5)], [record(images=1)]):
            with self.assertRaises(ValueError):
                aggregate(records, date(2026, 10, 7), 'ER_DR')

    def test_template_and_repeat_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second, third = [Path(folder) / f'{i}.xlsx' for i in range(3)]
            export_day(TEMPLATE, first, [record()], date(2026, 10, 7), 'ER_DR')
            export_day(TEMPLATE, second, [record('next', '2026-10-08T02:00:00')], date(2026, 10, 8), 'ER_DR', first)
            export_day(TEMPLATE, third, [record()], date(2026, 10, 7), 'ER_DR', second)
            source = openpyxl.load_workbook(TEMPLATE)['202610 AI 제거버전']
            result = openpyxl.load_workbook(third, data_only=True)['202610_ER_DR']
            self.assertEqual(result['B11'].value, 1)
            self.assertEqual(result['C11'].value, 2)
            self.assertEqual(result['C49'].value, 3)
            self.assertEqual(result['C87'].value, 1)
            self.assertIsNone(result['B87'].value)
            self.assertEqual(result['E12'].value, 2)
            self.assertEqual(result['Z36'].value, 2)
            self.assertEqual(result['AA36'].value, 4)
            self.assertIsNone(result['B5'].value)
            self.assertEqual(set(map(str, result.merged_cells.ranges)), set(map(str, source.merged_cells.ranges)))
            self.assertEqual(result['C11']._style, source['C11']._style)
            self.assertEqual(str(result.print_area), str(source.print_area).replace(source.title, result.title))
            self.assertEqual(result.page_setup, source.page_setup)


if __name__ == '__main__':
    unittest.main()
