"""One physical result oracle: experimental pressures, with a sourced allowance."""

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/heptane-vapor-pressure"
ANALYSIS = EXAMPLE / "analyses/vapor-pressure"


class HeptaneExampleTest(unittest.TestCase):
    def test_published_pressure_comparison(self):
        # CONTEXT.md derives 0.55 kPa from measurement uncertainty and rounding.
        # The measured values below are Busch et al., Table 2, heptane rows 2–5.
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(
                [sys.executable, str(ANALYSIS / "scripts/run.py"), temporary],
                check=True, capture_output=True, text=True,
            )
            with (Path(temporary) / "results/comparison.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([int(row["source_row"]) for row in rows], [2, 3, 4, 5])
            for row, temperature, observed in zip(
                rows, [303.2, 308.2, 313.1, 318.2], [8.0, 10.2, 12.4, 15.6]
            ):
                self.assertEqual(float(row["temperature_K"]), temperature)
                self.assertEqual(float(row["measured_kPa"]), observed)
                self.assertLessEqual(
                    abs(float(row["model_kPa"]) - observed), 0.55,
                    f"Table 2 row {row['source_row']}: model pressure disagrees with experiment",
                )


if __name__ == "__main__":
    unittest.main()
