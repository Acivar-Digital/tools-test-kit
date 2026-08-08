#!/bin/bash
rm -rf /home/yapilwsl/arthityap/baziforecaster/mutants/tests  # baziforeporter-only: not in standalone kit download
uv run pytest TEST/unit/engine/test_triggers.py TEST/math/test_ch07_luck_pillars.py TEST/math/test_ch11_synthesis.py -q -p no:cacheprovider -o addopts=
