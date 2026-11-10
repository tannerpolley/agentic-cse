from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from plugin.scripts.workflow import check_readiness


class ReadinessTests(unittest.TestCase):
    def test_report_separates_tex_commands_from_tinytex_profile(self) -> None:
        commands = {
            "git": "/usr/bin/git",
            "quarto": "/usr/local/bin/quarto",
            "lualatex": "/usr/bin/lualatex",
            "latexmk": "/usr/bin/latexmk",
            "snakemake": None,
            "cse-zotero": "/usr/local/bin/cse-zotero",
        }
        doctor = {
            "ok": False,
            "identity": {"package": {"name": "cse-zotero"}},
            "readiness": {
                "zotero_local_api": {"ready": False},
                "retained_corpus": {"ready": True},
                "data": {"ready": True},
                "mathpix": {"ready": False, "reason": "explicit library consent is not granted"},
            },
        }

        with (
            patch.object(check_readiness.shutil, "which", side_effect=commands.get),
            patch.object(
                check_readiness,
                "latex_check",
                return_value="active TeX distribution is /usr/share/texlive; expected TinyTeX",
            ) as latex,
            patch.object(
                check_readiness.subprocess,
                "run",
                return_value=check_readiness.subprocess.CompletedProcess(
                    ["cse-zotero", "doctor", "--json"], 1, stdout=json.dumps(doctor), stderr=""
                ),
            ) as run,
        ):
            output = check_readiness.report()

            commands["snakemake"] = "/usr/local/bin/snakemake"
            latex.return_value = "missing TeX file: beamer.cls"
            missing_class_output = check_readiness.report()

        self.assertEqual(2, run.call_count)
        self.assertEqual(2, latex.call_count)
        self.assertEqual(["/usr/local/bin/cse-zotero", "doctor", "--json"], run.call_args.args[0])
        self.assertIn("LuaLaTeX: present", output)
        self.assertIn("latexmk: present", output)
        self.assertIn("active TeX distribution is /usr/share/texlive", output)
        self.assertIn("Documents — partial", output)
        self.assertIn("Documents — partial", missing_class_output)
        self.assertIn("LaTeX toolchain check: missing TeX file: beamer.cls", missing_class_output)
        self.assertIn("cse:tikz", output)
        self.assertIn("Sources — partial", output)
        self.assertIn("Retained corpus: ready", output)
        self.assertIn("Mathpix: not ready (explicit library consent is not granted)", output)
