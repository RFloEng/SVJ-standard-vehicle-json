"""
SVJ Drivetrain Control Checker (v0.99.3)
=========================================
Cross-field rules for differential control that JSON Schema cannot express
(proposals/svj_differential_control_proposal.md, spec §10.6.1 and §10.8.1):
`lock_control` (dynamic differential lock) and `transfer_case.coupling`.

Used automatically by tools/validate.py; can also run standalone.

svj-py ships an identical copy as svj/drivetrain.py — keep the two files in sync
(tests/test_vehicle.py::test_drivetrain_checker_in_sync enforces it).

Usage:
    python tools/drivetrain_check.py <file.svj.json> [file2 ...]
"""

import json
import sys

NO_LOCK_TYPES = {"open", "locked", "spool"}


def _chains(lc):
    """lock_control may be one chain or an array of chains."""
    if isinstance(lc, dict):
        return [lc]
    if isinstance(lc, list):
        return [c for c in lc if isinstance(c, dict)]
    return []


def _check_lock_control(where, diff, errors, warnings):
    lc = diff.get("lock_control")
    if lc is None:
        return
    if diff.get("type") in NO_LOCK_TYPES:
        warnings.append(f"{where}.lock_control: differential type '{diff['type']}' has no lock to modulate")

    chains = _chains(lc)
    targets = [c.get("target") for c in chains]
    if len(chains) > 1:
        dup = sorted({t for t in targets if t is not None and targets.count(t) > 1})
        for t in dup:
            errors.append(f"{where}.lock_control: target '{t}' appears in more than one chain")
        if "lock" in targets and ("lock_power" in targets or "lock_coast" in targets):
            errors.append(
                f"{where}.lock_control: target 'lock' overlaps 'lock_power'/'lock_coast' in another chain"
            )

    for ci, chain in enumerate(chains):
        base = f"{where}.lock_control" + (f"[{ci}]" if isinstance(lc, list) else "")
        for si, st in enumerate(chain.get("stages") or []):
            if not isinstance(st, dict):
                continue
            sp = f"{base}.stages[{si}]"
            xs = [p[0] for p in (st.get("curve") or [])
                  if isinstance(p, list) and p and isinstance(p[0], (int, float))]
            if any(b <= a for a, b in zip(xs, xs[1:])):
                errors.append(f"{sp}.curve: x values must be strictly increasing")
            lo, hi = st.get("min"), st.get("max")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
                errors.append(f"{sp}: min ({lo}) is greater than max ({hi})")


def check(doc):
    errors, warnings = [], []
    pt = doc.get("powertrain")
    if not isinstance(pt, dict):
        return errors, warnings

    for i, d in enumerate(pt.get("differentials") or []):
        if isinstance(d, dict):
            _check_lock_control(f"powertrain.differentials[{i}] '{d.get('id', '?')}'", d, errors, warnings)

    tc = pt.get("transfer_case")
    if isinstance(tc, dict):
        if isinstance(tc.get("center_diff"), dict):
            _check_lock_control("powertrain.transfer_case.center_diff", tc["center_diff"], errors, warnings)

        cp = tc.get("coupling")
        if isinstance(cp, dict):
            ramp, mx = cp.get("ramp_torque"), cp.get("max_torque")
            if isinstance(ramp, (int, float)) and isinstance(mx, (int, float)) and ramp > mx:
                errors.append(
                    f"powertrain.transfer_case.coupling: ramp_torque ({ramp}) exceeds max_torque ({mx})"
                )
            if tc.get("type") in ("full_time", "part_time"):
                warnings.append(
                    f"powertrain.transfer_case.coupling: transfer_case.type '{tc['type']}' — "
                    "a torque-limited coupling implies 'on_demand'"
                )
        elif tc.get("type") == "on_demand" and "torque_split" not in tc:
            warnings.append(
                "powertrain.transfer_case: type 'on_demand' has neither torque_split nor coupling"
            )
    return errors, warnings


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    bad = False
    for path in argv:
        with open(path, "r", encoding="utf-8") as f:
            errs, warns = check(json.load(f))
        print(f"{path}: {len(errs)} error(s), {len(warns)} warning(s)")
        for w in warns:
            print(f"  WARN   {w}")
        for e in errs:
            print(f"  ERROR  {e}")
        bad = bad or bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
