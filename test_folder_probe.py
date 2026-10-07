import tempfile
import threading
import unittest
from pathlib import Path

from folder_probe import inspect_folder


class FolderProbeTests(unittest.TestCase):
    def test_inventory_contains_no_filenames(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'PRIVATE_PATIENT.db').write_bytes(b'PRIVATE_CONTENT')
            report = inspect_folder(folder, threading.Event())
            self.assertEqual(report['extension_counts'], {'.db': 1})
            self.assertEqual(report['dicom_part10_signatures'], 0)
            self.assertNotIn('PRIVATE', str(report))
            self.assertFalse(report['complete_today_dataset_verified'])

    def test_limit_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'a.dcm').write_bytes(b'not a DICOM')
            report = inspect_folder(folder, threading.Event(), max_files=0)
            self.assertTrue(report['file_limit_reached'])
            stop = threading.Event()
            stop.set()
            self.assertTrue(inspect_folder(folder, stop)['cancelled'])

    def test_dicom_metadata_without_values(self):
        import pydicom
        from pydicom.dataset import FileDataset, FileMetaDataset
        with tempfile.TemporaryDirectory() as folder:
            meta = FileMetaDataset()
            meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
            meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
            meta.SourceApplicationEntityTitle = 'PRIVATE_AE'
            data = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
            data.PatientName = 'PRIVATE_PATIENT'
            data.StudyDate = '20261007'
            data.Modality = 'DX'
            data.save_as(Path(folder, 'private.dcm'), enforce_file_format=True)
            report = inspect_folder(folder, threading.Event())
            self.assertEqual(report['metadata_field_presence_counts']['StudyDate'], 1)
            self.assertEqual(report['metadata_field_presence_counts']['SourceApplicationEntityTitle'], 1)
            self.assertNotIn('PRIVATE', str(report))
            self.assertNotIn('20261007', str(report))
