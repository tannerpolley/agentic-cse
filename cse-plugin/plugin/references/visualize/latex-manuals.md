# Local LaTeX manual catalog

Use this reference when an exact package option, command, library interface, build
behavior, or compatibility question cannot be answered from the package and
extension policies. The official manual remains authoritative; the local cache
is a searchable projection for agents.

## Local store

Run:

```bash
./scripts/visualize/cache-latex-manuals.sh
```

The script writes to:

```text
~/.local/share/cse/latex-manuals/
  INDEX.md
  text/
    <package>--<manual>.txt
  cli/
    quarto-help.txt
    pandoc-help.txt
```

The converted text is generated from the official manuals installed by TeX
Live. It is not committed to the plugin because it is large and toolchain
specific. TeX Live source files remain under the active TinyTeX `texmf-dist`
tree and can be located with `kpsewhich`.

## Agent lookup route

1. Read `INDEX.md` to find the package and local manual file.
2. Search the smallest relevant manual with `rg`, using the command, key, or
   error text as the first query.
3. Read the surrounding section, including version notes and examples.
4. Confirm the installed package version with `tlmgr info <package>`.
5. Reproduce uncertain syntax in a minimal document before integrating it.

Examples:

```bash
manuals="$HOME/.local/share/cse/latex-manuals"
rg -n -i 'table-format|uncertainty' "$manuals/text/siunitx"*.txt
rg -n -i 'boxplot.*draw direction' "$manuals/text/pgfplots"*.txt
rg -n -i 'node family|span horizontal' "$manuals/text/tikz-ext"*.txt
```

## Source priority

1. Installed official manual matching the active package version.
2. Installed `.dtx`, `.tex`, or package implementation located with
   TinyTeX's `kpsewhich` when the manual and behavior disagree.
3. Official project documentation or CTAN package page.
4. A minimal compile against the exact document class and engine.

Do not promote a web snippet, generated example, or remembered syntax over the
installed manual and executable result.

## Manual families cached

- workflow and profiles: Quarto, Pandoc, Beamer, and Moloch;
- engine and typography: `fontspec`, `unicode-math`, `microtype`, and
  `mathtools`;
- scientific notation: `siunitx`, `mhchem`, `derivative`, and `nicematrix`;
- tables and terminology: `booktabs`, `threeparttable`, `csvsimple`,
  `tabularray`, and `glossaries-extra`;
- diagrams and plots: PGF/TikZ, PGFPlots, `tikz-ext`, `chemfig`, `chemplants`,
  `chempid`, `circuitikz`, `forest`, `standalone`, and `adjustbox`;
- authoring infrastructure: `hyperref`, `cleveref`, `biblatex`, `tcolorbox`,
  `algorithmicx`, and `minted`.

The package policy lists additional narrow or alternative tools. Add one to
the cache script only when an agent needs its exact manual; the CTAN/TeX Live
package name is the cache key.
