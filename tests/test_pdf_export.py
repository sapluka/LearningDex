import os
import tempfile
import unittest
from unittest import mock

from app import main, pdf_export


class TestPdfExport(unittest.TestCase):
    def test_path_is_safe_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            first = pdf_export.pdf_path(root, '纹理:映射/采样', 'BV1TEST')
            self.assertEqual(os.path.basename(first), '纹理_映射_采样（BV1TEST）.pdf')
            open(first, 'wb').close()
            second = pdf_export.pdf_path(root, '纹理:映射/采样', 'BV1TEST')
            self.assertTrue(second.endswith('（2）.pdf'))

    def test_generate_pdf_uses_configured_directory(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {'output_dir': os.path.join(root, 'notes'),
                       'pdf_output_dir': os.path.join(root, 'pdf')}
            api.current_taskdir = os.path.join(root, 'notes', 'BV1TEST')
            os.makedirs(api.current_taskdir)
            with mock.patch.object(pdf_export, 'print_current_page') as render, \
                 mock.patch.object(main.webview, 'windows', [object()]):
                result = api.generate_pdf('# 内容', '纹理映射')
            self.assertTrue(result['ok'])
            self.assertTrue(result['path'].startswith(api.cfg['pdf_output_dir']))
            self.assertTrue(result['path'].endswith('纹理映射（BV1TEST）.pdf'))
            self.assertTrue(os.path.isfile(os.path.join(api.current_taskdir, 'final.md')))
            render.assert_called_once()

    def test_pdf_engine_error_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {'output_dir': root}
            with mock.patch.object(pdf_export, 'print_current_page', side_effect=Exception('渲染失败')), \
                 mock.patch.object(main.webview, 'windows', [object()]):
                result = api.generate_pdf('# 内容', '标题')
            self.assertFalse(result['ok'])
            self.assertIn('渲染失败', result['error'])


if __name__ == '__main__':
    unittest.main()
