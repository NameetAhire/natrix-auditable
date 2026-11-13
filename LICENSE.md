# Licence

This repository is dual-licensed by component.

## Code: MIT

Copyright (c) 2026 Nameet Sudam Ahire and D. D. Ambawade

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Documentation, tables, figures and manuscript source: CC BY 4.0

The documentation, generated tables, figures, and manuscript source in this
repository are licensed under the Creative Commons Attribution 4.0
International License (CC BY 4.0):

<https://creativecommons.org/licenses/by/4.0/legalcode>

You may share and adapt this material for any purpose, including commercial
use, provided that you give appropriate credit, link to the licence, and
indicate whether changes were made. A suggested attribution is the manuscript
citation plus the repository URL:

> Ahire Nameet Sudam and D. D. Ambawade, "NATRIX: An Auditable
> Feature-Admission and Promotion Protocol for Inline HTTP Attack Detection,"
> 2026. <https://github.com/NameetAhire/natrix-auditable>

## Third-party material

This repository does **not** redistribute the raw HTTP corpora. Their sources
and licences are recorded in `NATRIX_Q1_Manuscript/data/README.md` and
`NATRIX_Q1_Manuscript/data/manifest.json`:

- CSIC 2010: public research dataset; cite Torrano-Gimenez, Perez-Villegas and
  Alvarez (2010).
- ECML/PKDD 2007: public research dataset; cite the ECML/PKDD 2007 challenge.
- SR-BH 2020: CC0 1.0; cite Sureda Riera et al., Computers & Security 120
  (2022) 102788.
- OpenAppSec WAF Comparison Project: Apache 2.0 for the legitimate traffic and
  mixed licences for the payload collections; see the upstream repository.

Tectonic, the Temurin JRE, `tla2tools.jar`, ModSecurity CRS and the
`owasp/modsecurity-crs` image are third-party tools and are not authored here.
They are not included in the repository; their own licences apply.

The eight files under `Ai-Agent/` are unmodified production modules authored by
the manuscript authors and are included under the MIT licence above so that the
evaluation and latency harness remain runnable.
