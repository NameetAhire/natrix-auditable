"""Generate data/manifest.json with provenance and checksums for every raw file."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FILES = [
    {
        "id": "csic_2010_normal_train",
        "dataset": "CSIC 2010",
        "path": "data/raw/csic/mirror/cisc_normalTraffic_train.txt",
        "source": "https://github.com/msudol/Web-Application-Attack-Datasets",
        "original": "http://www.isi.csic.es/dataset/ (unreachable; IMPACT record https://www.impactcybertrust.org/dataset_view?idDataset=940)",
        "license": "Public research dataset; cite the original authors",
        "citation": "Torrano-Gimenez, C., Perez-Villegas, A., Alvarez, G. HTTP dataset CSIC 2010 (2010).",
        "notes": "Byte-identical to the published mirror archive.",
    },
    {
        "id": "csic_2010_normal_test",
        "dataset": "CSIC 2010",
        "path": "data/raw/csic/mirror/cisc_normalTraffic_test.txt",
        "source": "https://github.com/msudol/Web-Application-Attack-Datasets",
        "original": "http://www.isi.csic.es/dataset/",
        "license": "Public research dataset; cite the original authors",
        "citation": "Torrano-Gimenez, C., Perez-Villegas, A., Alvarez, G. HTTP dataset CSIC 2010 (2010).",
    },
    {
        "id": "csic_2010_anomalous_test",
        "dataset": "CSIC 2010",
        "path": "data/raw/csic/mirror/cisc_anomalousTraffic_test.txt",
        "source": "https://github.com/msudol/Web-Application-Attack-Datasets",
        "original": "http://www.isi.csic.es/dataset/",
        "license": "Public research dataset; cite the original authors",
        "citation": "Torrano-Gimenez, C., Perez-Villegas, A., Alvarez, G. HTTP dataset CSIC 2010 (2010).",
    },
    {
        "id": "csic_2010_archive",
        "dataset": "CSIC 2010",
        "path": "data/raw/csic/csic_2010_mirror.tar.gz",
        "source": "https://raw.githubusercontent.com/msudol/Web-Application-Attack-Datasets/master/OriginalDataSets/csic_2010/dataset_cisc_train_test.tar.gz",
        "license": "Public research dataset",
        "citation": "Torrano-Gimenez, C., Perez-Villegas, A., Alvarez, G. HTTP dataset CSIC 2010 (2010).",
    },
    {
        "id": "srbh_2020",
        "dataset": "SR-BH 2020",
        "path": "data/raw/srbh/srbh_2020.csv",
        "source": "https://dataverse.harvard.edu/api/access/datafile/6319496",
        "original": "https://doi.org/10.7910/DVN/OGOIXX",
        "license": "CC0 1.0",
        "citation": "Sureda Riera, T., Bermejo Higuera, J.-R., Bermejo Higuera, J., Martinez Herraiz, J.-J., Sicilia Montalvo, J.-A. A new multi-label dataset for Web attacks CAPEC classification using machine learning techniques. Computers & Security 120 (2022) 102788. https://doi.org/10.1016/j.cose.2022.102788",
        "notes": "907,815 parsed rows; 422,054 unique after exact deduplication.",
    },
    {
        "id": "ecml_pkdd_2007_archive",
        "dataset": "ECML/PKDD 2007",
        "path": "data/raw/ecml/ecml_pkdd_train_test.tar.gz",
        "source": "https://raw.githubusercontent.com/msudol/Web-Application-Attack-Datasets/master/OriginalDataSets/ecml_pkdd/dataset_ecml_pkdd_train_test.tar.gz",
        "original": "ECML/PKDD 2007 Discovery Challenge",
        "license": "Public research dataset",
        "citation": "ECML/PKDD 2007 Discovery Challenge on web attack detection.",
        "notes": "xml_train.txt (24,504 Valid) + xml_test.txt (10,502 Valid + 15,110 attack) reconstitute the official 50,116-record training set.",
    },
    {
        "id": "openappsec_legitimate",
        "dataset": "OpenAppSec WAF Comparison Project",
        "path": "data/raw/openappsec/legitimate.zip",
        "source": "https://downloads.openappsec.io/waf-comparison-project/legitimate.zip",
        "original": "https://github.com/openappsec/waf-comparison-project",
        "license": "Apache 2.0",
        "citation": "OpenAppSec WAF Comparison Project, Legitimate Requests Dataset (2024).",
        "notes": "692 site files; deterministic stratified sample of 200 requests per site.",
    },
    {
        "id": "openappsec_malicious",
        "dataset": "OpenAppSec WAF Comparison Project",
        "path": "data/raw/openappsec/malicious.zip",
        "source": "https://downloads.openappsec.io/waf-comparison-project/malicious.zip",
        "original": "https://github.com/openappsec/waf-comparison-project",
        "license": "Mixed, mostly MIT (MGM WAF Payload Collection)",
        "citation": "OpenAppSec WAF Comparison Project, Malicious Requests Dataset (2024).",
        "notes": "73,924 payloads across 7 attack families.",
    },
]


def main() -> None:
    entries = []
    for spec in FILES:
        path = C.ROOT / spec["path"]
        if not path.exists():
            entries.append({**spec, "present": False})
            continue
        entries.append(
            {
                **spec,
                "present": True,
                "bytes": path.stat().st_size,
                "sha256": C.sha256_file(path),
                "retrieved": date.today().isoformat(),
            }
        )
    C.write_json(C.ROOT / "data" / "manifest.json", {"generated": date.today().isoformat(), "files": entries})
    for entry in entries:
        status = entry.get("sha256", "MISSING")[:16]
        print(f"{entry['id']:<28} {entry.get('bytes', 0):>12,}  {status}")


if __name__ == "__main__":
    main()
