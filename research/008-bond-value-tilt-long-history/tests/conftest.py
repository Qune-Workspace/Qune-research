"""Study 008 only (new file; every copied test file stays byte-identical).

Two copied tests of Study 007's forward record read Study 007's committed
episode output (``results/episode/summary.json``), which this study's folder
does not have until its own episode runs, and which would then be Study 008's,
not 007's.  They test Study 007's code against Study 007's results and keep
running, unchanged, in Study 007's own suite (CI matrix).  Here they are
skipped by name with that reason (decided 2026-10-25, BUILD_LOG); nothing else
is skipped.  Study 008's own forward tests come with ``forward008.py``.
"""

import pytest

SKIPPED_HERE = {
    "tests/test_forward007.py::test_starting_weights_are_the_episodes",
    "tests/test_forward007.py::test_frozen_rank_history_reproduces_the_episode_starting_weights",
}
REASON = "reads Study 007's results/episode/; runs in Study 007's own suite (tests/conftest.py)"


def pytest_collection_modifyitems(config, items):
    found = set()
    for item in items:
        node = item.nodeid.split("research/008-bond-value-tilt-long-history/")[-1]
        if node in SKIPPED_HERE:
            item.add_marker(pytest.mark.skip(reason=REASON))
            found.add(node)
    collected_all = any(i.nodeid.endswith("test_forward007.py::test_records_never_rewritten") for i in items)
    if collected_all and found != SKIPPED_HERE:
        raise pytest.UsageError(f"tests/conftest.py: expected to skip {sorted(SKIPPED_HERE)}, found {sorted(found)}")
