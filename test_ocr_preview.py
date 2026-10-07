import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ocr_preview import recognize


class Image:
    def save(self, buffer, format):
        buffer.write(b'fake-png-for-transport-test')


class OCRTests(unittest.TestCase):
    @patch('ocr_preview.platform.system', return_value='Windows')
    @patch('ocr_preview.subprocess.run')
    def test_local_transport(self, run, platform):
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps({'ok': True, 'lines': [{'text': 'DX'}]}))
        self.assertEqual(recognize(Image())['lines'][0]['text'], 'DX')
        command = run.call_args.args[0]
        self.assertNotIn('-ExecutionPolicy', command)
        self.assertIn('-File', command)

    @patch('ocr_preview.platform.system', return_value='Windows')
    @patch('ocr_preview.subprocess.run')
    def test_missing_language(self, run, platform):
        run.return_value = SimpleNamespace(returncode=1, stdout='{"ok":false,"error":"OCR_LANGUAGE_MISSING"}')
        with self.assertRaisesRegex(RuntimeError, 'en-US'):
            recognize(Image())

    @patch('ocr_preview.platform.system', return_value='Windows')
    @patch('ocr_preview.subprocess.run')
    def test_invalid_output_does_not_leak(self, run, platform):
        run.return_value = SimpleNamespace(returncode=1, stdout='PRIVATE_SCREEN_TEXT')
        with self.assertRaises(RuntimeError) as result:
            recognize(Image())
        self.assertNotIn('PRIVATE_SCREEN_TEXT', str(result.exception))
