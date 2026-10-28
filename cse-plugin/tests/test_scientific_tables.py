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
            source.write_text(r"""\begin{tabular}{l S[table-format=3.2] p{2cm} S S}
\toprule
Item & {Value} & Description & {Value} & {Value} \\
A & 3.4 & text & 2 & 1.25 \\
B & \tablenum[table-format=3.2,round-precision=2]{1.25} & text & 2 & 3 \\
\bottomrule
\end{tabular}
\begin{longtable}{l S}
\caption{Conditions $T=300$ and $P=1$} \\
A & 1 \\
\end{longtable}
""")
            result = subprocess.run([sys.executable, str(script), '--tex', str(source), '--warnings-as-errors'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(result.stdout.strip())
            source.write_text(r'\begin{tabular}{p{2cm}}\num{1.25} \\ \end{tabular}')
            result = subprocess.run([sys.executable, str(script), '--tex', str(source), '--warnings-as-errors'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('numeric p{}', result.stdout)
            source.write_text(r'\begin{tabular}{l X p{2cm}}A & B & 3.4 \\ \end{tabular}')
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
