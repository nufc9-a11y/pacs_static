"""Generate fictitious examples without connecting to PACS."""
from datetime import date
from pathlib import Path

from pacs_statistics import export_day


def generate_demo(output_dir):
    output_dir = Path(output_dir)
    root = Path(__file__).resolve().parent
    records = []
    for ae in ('ER_DR', 'ER_M', 'DR9', 'DR10', 'DR19'):
        for index, (hour, series, images) in enumerate(((1, 2, 2), (2, 2, 3), (14, 3, 4))):
            records.append(dict(study_id=f'DEMO-{ae}-{index}',
                                study_datetime=f'2026-10-07T{hour:02d}:30:00',
                                source_aetitle=ae, modality='DX\\PR',
                                series_count=series, instance_count=images, is_chest=True))
    outputs = []
    for ae in ('ER_DR', 'ER_M', 'DR9', 'DR10', 'DR19'):
        target = output_dir / f'DEMO_20261007_{ae}.xlsx'
        export_day(root / 'templates' / 'statistics_blank.xlsx', target,
                   records, date(2026, 10, 7), ae)
        outputs.append(target)
    return outputs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='output/demo')
    args = parser.parse_args()
    for path in generate_demo(args.output_dir):
        print(path)
