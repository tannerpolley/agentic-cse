# Retained input provenance

Retrieved 2026-11-10. Both primary papers were downloaded, opened, and read in
full for this task. The relevant table pages were also rendered and inspected;
no figure was digitized. Paper files remain in `/tmp/issue-36-sources/` during
preparation and are **not** part of the example. Reproduction is offline.

## Measurements: Busch et al. (2026)

Christoph Busch, Marvin Kasterke, Thorsten Brands, André Bardow, and Carsten
Flake, *An Automated Milliliter-Scale Setup for Vapor–Liquid Equilibrium
Measurements with Raman Spectroscopy: Validation with Binary Mixtures Ranging
from 2 to 98 kPa and 278–343 K*, DOI
[10.1021/acs.jced.5c00843](https://doi.org/10.1021/acs.jced.5c00843).

Retrieved file: <https://publications.rwth-aachen.de/record/1032996/files/1032996.pdf>

SHA-256: `63a012b9ec43d818b90c104d3cd74c1749552da577fd3662586b4ba74067b0b0`

This is the 12-page early publication PDF with lettered pages A–L and
placeholder final pagination. Use PDF p. 8, letter H, **Table 2, heptane T/K and
p/kPa columns**, counting data rows from 1 after the headings:

| Source row | T (K), verbatim | p (kPa), verbatim | Use |
| --- | ---: | ---: | --- |
| 1 | 298.2 | 6.2 | Excluded: below model range |
| 2 | 303.2 | 8.0 | Comparison |
| 3 | 308.2 | 10.2 | Comparison |
| 4 | 313.1 | 12.4 | Comparison |
| 5 | 318.2 | 15.6 | Comparison |

`measurements.csv` is a manual transcription of these five pairs, with units
preserved. Table 2 footnote a on the same page supplies expanded U(p)=0.3 kPa
and U(T)=0.115 K + 0.002|t/°C| K, both with coverage factor k=2.
Table 1, heptane row and footnote a, supplies the purity and mass-basis finding
recorded in the scientific context. Section 2.2.2 describes the pressure measurements.

**Licence finding:** the first page explicitly says CC-BY 4.0. The
[repository record](https://publications.rwth-aachen.de/record/1032996) also
identifies CC BY 4.0. The extracted values here are attributed to all authors,
with table/row locators and a link to the
[licence](https://creativecommons.org/licenses/by/4.0/). Redistribution with
attribution is allowed. The adaptation is transcription to CSV, selection of
four rows by model domain, and addition of model results; no source values
are corrected. This attribution and licence notice must accompany the data.

The ACS publisher PDF endpoint returned HTTP 403. The RWTH endpoint initially
returned its JavaScript initialization page. Downloading with its public
`APP_INIT=1` initialization cookie returned the PDF above:

```bash
curl -fL -b 'APP_INIT=1' \
  'https://publications.rwth-aachen.de/record/1032996/files/1032996.pdf' \
  -o busch-2026.pdf
sha256sum busch-2026.pdf
```

## Parameters: Willingham et al. (1945)

Charles B. Willingham, William J. Taylor, Joan M. Pignocco, and Frederick D.
Rossini, *Vapor Pressures and Boiling Points of Some Paraffin,
Alkylcyclopentane, Alkylcyclohexane, and Alkylbenzene Hydrocarbons*, Journal of
Research of the National Bureau of Standards 35, 219–244, DOI
[10.6028/jres.035.009](https://doi.org/10.6028/jres.035.009).

Retrieved file: <https://nvlpubs.nist.gov/nistpubs/jres/35/jresv35n3p219_A1b.pdf>

SHA-256: `d9687895ce24d7bd4439896a950259c771d432582e54dd2486a37a9152e848ef`

PDF p. 21, printed p. 239, **Table 3, n-Heptane row** (eighth paraffin row)
supplies A=6.90342, B=1268.636, C=216.951, with **p in mm Hg and t in °C**
in the table heading. It gives the range 25.9–99.3 °C, 48–780 mm Hg.
Equation (2), pp. 233–234, defines the correlation. Section VI.2, p. 238,
states that the later series supplied the coefficients where two series
exist: for heptane this is Table 2's April 10, 1943 series. Only the coefficients
are taken; the 1945 observations are not validation data here. The 2026
experiments could not have been used to fit this 1945 model.

**Rights finding:** this NBS research paper contains no separate copyright
restriction. The [NIST Library FAQ](https://www.nist.gov/nist-research-library/library-faqs),
“Do I need reprint permission to use material from a NIST publication?”,
states that federal NIST publications are generally public domain in the United
States, need no reprint permission, and should be credited. Its statement also
covers public-domain official writing published in copyrighted periodicals.
Credit: Reprinted courtesy of the National Institute of Standards and
Technology, U.S. Department of Commerce. Not copyrightable in the United States.
This is a U.S. public-domain finding, not a worldwide rights opinion.

Retrieved FAQ HTML SHA-256:
`8c20b0da57c0e3bb6d6ae3612b836cc189e6f13fbb22b6eb11b33f211a6023de`.

## Unit conventions: NIST SP 811

The [Chapter 4 page](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes),
Section 4.2.1.1, supplies `t/°C = T/K - 273.15` and the SI prefix table gives
kilo=10³. Retrieved HTML SHA-256:
`118d3775689e414ce57777b492c79f3fe3fd4e81d4e30320b3b50eb44fc44543`.

The [Appendix B.8 page](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8),
M table, “millimeter of mercury, conventional (mmHg)” row, supplies
1.333224 E+02 Pa/mmHg. Thus 133.3224/1000 = 0.1333224 kPa/mmHg.
Retrieved HTML SHA-256:
`889561d7dbd99167c2ea647f86d9c01b1f837b2bceb8aa310cd46c5b6cfbc9c1`.

The conversion constants are conventions, not experimental inputs. They are
credited federal NIST material under the same general public-domain finding.
HTML files can change their hash because of site navigation or other page
updates; the locators and factors above identify the content used.
