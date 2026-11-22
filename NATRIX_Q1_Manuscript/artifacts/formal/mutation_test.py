"""Mutation testing for the CPPP TLA+ specification.

A model check that passes can be vacuous if the invariants are true by
construction.  This script removes one guard at a time and asks TLC whether the
corresponding invariant is now violated.  A mutant that TLC kills is evidence
that the invariant is sensitive to the transition it is supposed to constrain;
a mutant that survives would be a specification defect.

The mutants are generated from the checked-in Cppp.tla, not hand-written, so
the diff is a single guard in each case.

Run
---
    python artifacts/formal/mutation_test.py

Outputs
-------
    artifacts/formal/mutants/<name>/Cppp.tla
    artifacts/formal/mutants/<name>/Cppp_small.cfg
    artifacts/formal/mutation_results.json
    artifacts/formal/mutation_results.md
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FORMAL = Path(__file__).resolve().parent
ROOT = FORMAL.parents[1]
JAR = ROOT / "tools" / "tla2tools.jar"
JAVA = next((ROOT / "tools" / "jre17").rglob("java.exe"), None)
BASE = FORMAL / "Cppp.tla"
CFG = FORMAL / "Cppp_small.cfg"
OUT = FORMAL / "mutants"

DIRECT_PROMOTE = '''
\\* Mutant: an observed rule can be promoted without a canary.
DirectPromote(r) ==
  /\\ state[r] = "observed"
  /\\ state' = [state EXCEPT ![r] = "promoted"]
  /\\ activePolicy' = activePolicy \\cup {r}
  /\\ audit' = audit \\cup {r}
  /\\ UNCHANGED <<votes, trust, canaryPassed, canarySeen, canaryHit>>
'''


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one occurrence of:\n{old}\nfound {text.count(old)}")
    return text.replace(old, new)


def mutants() -> dict[str, tuple[str, str]]:
    base = BASE.read_text(encoding="utf-8")
    out: dict[str, tuple[str, str]] = {}

    # 1. Remove the quorum guard from both the canary start and promotion.
    text = base
    text = replace_once(
        text,
        "  /\\ Cardinality(votes[r]) >= K\n  /\\ trust[r] >= Tau\n  /\\ state' = [state EXCEPT ![r] = \"canary\"]",
        "  /\\ trust[r] >= Tau\n  /\\ state' = [state EXCEPT ![r] = \"canary\"]",
    )
    text = replace_once(
        text,
        "PassCanary(r) ==\n  /\\ state[r] = \"canary\"\n  /\\ Cardinality(votes[r]) >= K\n  /\\ trust[r] >= Tau",
        "PassCanary(r) ==\n  /\\ state[r] = \"canary\"\n  /\\ trust[r] >= Tau",
    )
    text = replace_once(
        text,
        "  /\\ canaryPassed[r]\n  /\\ Cardinality(votes[r]) >= K\n  /\\ trust[r] >= Tau",
        "  /\\ canaryPassed[r]\n  /\\ trust[r] >= Tau",
    )
    out["no_quorum"] = (text, "NoPromotionWithoutQuorum")

    # 2. Promote without the canary outcome.
    text = replace_once(
        base,
        "  /\\ canaryPassed[r]\n  /\\ Cardinality(votes[r]) >= K",
        "  /\\ Cardinality(votes[r]) >= K",
    )
    out["no_canary"] = (text, "NoPromotionWithoutCanary")

    # 3. Promote after trust has decayed below the floor.
    text = replace_once(
        base,
        "  /\\ Cardinality(votes[r]) >= K\n  /\\ trust[r] >= Tau\n  /\\ state' = [state EXCEPT ![r] = \"promoted\"]",
        "  /\\ Cardinality(votes[r]) >= K\n  /\\ state' = [state EXCEPT ![r] = \"promoted\"]",
    )
    out["no_trust"] = (text, "NoPromotionWithoutTrust")

    # 4. Promote without writing the audit record.
    text = replace_once(
        base,
        "  /\\ audit' = audit \\cup {r}\n  /\\ UNCHANGED <<votes, trust, canaryPassed, canarySeen, canaryHit>>",
        "  /\\ audit' = audit\n  /\\ UNCHANGED <<votes, trust, canaryPassed, canarySeen, canaryHit>>",
    )
    out["no_audit"] = (text, "ActiveImpliesAudited")

    # 5. Add a direct observed -> promoted transition.
    text = replace_once(
        base,
        "Reject(r) ==",
        DIRECT_PROMOTE + "\nReject(r) ==",
    )
    text = replace_once(
        text,
        "  \\/ \\E r \\in Rules : SeedTrust(r) \\/ StartCanary(r) \\/ PassCanary(r) \\/ Retire(r) \\/ Reject(r)",
        "  \\/ \\E r \\in Rules : SeedTrust(r) \\/ StartCanary(r) \\/ PassCanary(r) \\/ Retire(r) \\/ Reject(r) \\/ DirectPromote(r)",
    )
    out["direct_promote"] = (text, "NoDirectPromotion")

    # 6. Retire a rule but leave it in the active policy.
    text = replace_once(
        base,
        "  /\\ state' = [state EXCEPT ![r] = \"retired\"]\n  /\\ activePolicy' = activePolicy \\ {r}",
        "  /\\ state' = [state EXCEPT ![r] = \"retired\"]\n  /\\ activePolicy' = activePolicy",
    )
    out["retired_active"] = (text, "RetiredNotActive")

    # 7. Pass the canary after a benign hit.
    text = replace_once(
        base,
        "  /\\ canarySeen[r] >= CanaryObs\n  /\\ ~canaryHit[r]\n  /\\ canaryPassed'",
        "  /\\ canarySeen[r] >= CanaryObs\n  /\\ canaryPassed'",
    )
    out["canary_hit"] = (text, "NoPromotionWithCanaryHit")

    # 8. Pass the canary without the observation budget.
    text = replace_once(
        base,
        "  /\\ trust[r] >= Tau\n  /\\ canarySeen[r] >= CanaryObs\n  /\\ ~canaryHit[r]",
        "  /\\ trust[r] >= Tau\n  /\\ ~canaryHit[r]",
    )
    out["no_observations"] = (text, "NoPromotionWithoutObservations")

    return out


def run_tlc(directory: Path, config: str = "Cppp_small.cfg") -> tuple[int, str]:
    cmd = [
        str(JAVA),
        "-XX:+UseParallelGC",
        "-cp",
        str(JAR),
        "tlc2.TLC",
        "-config",
        config,
        "-workers",
        "4",
        "Cppp.tla",
    ]
    result = subprocess.run(cmd, cwd=directory, text=True, capture_output=True, timeout=300)
    return result.returncode, result.stdout + "\n" + result.stderr


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"missing {BASE}")
    if not JAR.exists():
        raise SystemExit(f"missing {JAR}")
    if JAVA is None:
        raise SystemExit("missing bundled Java 17 runtime")
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, (text, expected) in mutants().items():
        directory = OUT / name
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        (directory / "Cppp.tla").write_text(text, encoding="utf-8")
        shutil.copy(CFG, directory / "Cppp_small.cfg")
        config = "Cppp_small.cfg"
        if name == "direct_promote":
            # NoDirectPromotion and NoPromotionWithoutCanary are the same
            # state predicate in this model; isolate the former so TLC reports
            # the invariant the mutant was designed to test.
            config = "Cppp_direct.cfg"
            (directory / config).write_text(
                "SPECIFICATION Spec\n\n"
                "CONSTANTS\n"
                "    Agents = {a1, a2, a3}\n"
                "    PolicyAgent = a1\n"
                "    Rules = {r1}\n"
                "    K = 2\n"
                "    Tau = 2\n"
                "    MaxTrust = 3\n"
                "    CanaryObs = 2\n\n"
                "INVARIANTS\n"
                "    TypeOK\n"
                "    NoDirectPromotion\n",
                encoding="utf-8",
            )
        code, output = run_tlc(directory, config)
        (directory / "tlc.log").write_text(output, encoding="utf-8")
        violated = sorted(set(re.findall(r"Invariant (\w+) is violated", output)))
        killed = bool(violated)
        rows.append(
            {
                "mutant": name,
                "expected_invariant": expected,
                "killed": killed,
                "violated": violated,
                "exit_code": code,
                "matched_expected": expected in violated,
            }
        )
        print(f"{name}: killed={killed} violated={violated} exit={code}", flush=True)

    result = {
        "base_spec": str(BASE.relative_to(ROOT)),
        "config": str(CFG.relative_to(ROOT)),
        "java": str(JAVA.relative_to(ROOT)),
        "mutants": rows,
        "killed": sum(1 for row in rows if row["killed"]),
        "total": len(rows),
        "all_expected": all(row["matched_expected"] for row in rows),
    }
    (FORMAL / "mutation_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# TLA+ mutation test",
        "",
        "Each mutant removes one guard from the checked-in `Cppp.tla`. A mutant is",
        "killed when TLC reports the expected invariant violation.",
        "",
        "| mutant | expected invariant | killed | violated |",
        "|---|---|:--:|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['mutant']}` | `{row['expected_invariant']}` | "
            f"{'yes' if row['killed'] else 'no'} | {', '.join(row['violated']) or '-'} |"
        )
    lines.append("")
    lines.append(f"Killed {result['killed']}/{result['total']} mutants; all expected: {result['all_expected']}.")
    (FORMAL / "mutation_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
