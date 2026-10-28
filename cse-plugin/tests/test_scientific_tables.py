import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScientificTablesTest(unittest.TestCase):
    def test_source_lint(self):
        script = ROOT / 'plugin/scripts/visualize/latex_visual_qa.py'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'table.tex'
            source.write_text('\\begin{tabular}{lp{2cm}}\nA = 1; B = 2 & 3.4 \\\\\n\\end{tabular}\n')
            result = subprocess.run([sys.executable, str(script), '--tex', str(source), '--warnings-as-errors'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('packed values', result.stdout)
            self.assertIn('numeric p{}', result.stdout)
            source.write_text('\\begin{tabular}{l S}\nItem & {Value} \\\\\nA & 3.4 \\\\\n\\end{tabular}\n')
            result = subprocess.run([sys.executable, str(script), '--tex', str(source), '--warnings-as-errors'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(result.stdout.strip())

    def test_helper(self):
        path = ROOT / 'plugin/assets/visualize/scientific_table.py'
        spec = importlib.util.spec_from_file_location('scientific_table', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        columns = [module.Column('Item', 'label'), module.Column('Mass', 'number', r'\si{\kg}', 2), module.Column('Source', 'citation')]
        for long in (False, True):
            output = module.table(columns, ['Group', ['A', 1.25, r'\cite{x}'], ['B', None, '[2]']], 'Caption', 'Note.', long)
            self.assertIn('{l S l}', output)
            self.assertIn(r'{Mass (\si{\kg})}', output)
            self.assertIn('A & 1.25', output)
            self.assertIn('{--}', output)
            self.assertIn(r'\multicolumn{3}', output)
            self.assertIn('Caption Note.', output)


if __name__ == '__main__':
    unittest.main()
