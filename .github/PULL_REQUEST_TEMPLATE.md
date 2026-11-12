## Summary

<!-- Describe what this PR changes and why. -->

## Verification Checklist

- [ ] `bin/vibeasm doctor` passes.
- [ ] `python3 -m unittest discover -s tests -v` passes with zero failures.
- [ ] `bin/vibeasm verify --quick` passes for all installed solutions.
- [ ] `make all && make examples && make clean` builds cleanly without warnings.
- [ ] No files in `solutions/` were edited by hand (all solutions installed via `vibeasm run` or `vibeasm accept`).
- [ ] If a verification gate was changed, a regression `.s` file was added to `tests/zoo/`.
