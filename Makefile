# Qune research: one entry point for what an outside reader can run.
#
#   make venv           create .venv and install every pinned requirement
#   make test           every study's unit tests, exactly as CI runs them
#   make lint           ruff over the repository, mypy over the shared library
#   make coverage       line coverage of the shared library (tests excluded)
#   make reproduce      the independent reviewers' recomputation of every published
#                       statistic in Studies 003 to 006 from the committed result
#                       files, then tools/effect_lines.py for 006-008's headline t
#   make reproduce-raw  the same for Studies 001, 002, 007 and 008, whose scripts
#                       need the raw vendor files in data/raw/ (not redistributed)
#   make charts         redraw every chart from the committed result files
#                       (rewrites charts/; `git diff --stat` shows any change)
#   make tearsheets     redraw the post-hoc tear-sheets in tearsheets/ from the
#                       committed monthly files and check them against the
#                       committed metrics files (exits 1 on any difference)
#   make dashboard      regenerate dashboard/ (the paper dashboard) from the
#                       studies' committed paper-log/ folders; nothing fetched
#
# Nothing here fetches data or runs a backtest: those paths stay behind each
# study's reproduce.sh, its APPROVED file and the raw files it refuses without.
# Every target uses the repository's virtual environment when it exists and
# python3 otherwise, as the reproduce scripts do.

ROOT   := $(abspath .)
PYTHON ?= $(if $(wildcard $(ROOT)/.venv/bin/python),$(ROOT)/.venv/bin/python,python3)

STUDIES := research/001-slope-duration-switch \
           research/002-slope-duration-switch-r \
           research/003-bond-tsmom-ief \
           research/004-xasset-trend-voltarget \
           research/005-duration-trend-regime \
           research/006-term-spread-switch-long-history \
           research/007-bond-carry-tilt-long-history \
           research/008-bond-value-tilt-long-history
SUITES  := $(STUDIES) qune_research desk-view

# review_recompute.py scripts that run from the committed outputs alone.  Rows
# that need the raw vendor files are reported as "not checked" when data/raw/
# is absent.  Studies 004 and 005 exit 1 by design: their reviews found README
# figures one unit off in the last printed digit, disclosed and answered in
# REVIEW.md, and the scripts still count them as mismatches.
RECOMPUTE     := research/003-bond-tsmom-ief \
                 research/004-xasset-trend-voltarget \
                 research/005-duration-trend-regime \
                 research/006-term-spread-switch-long-history
# Studies 007 and 008's scripts check almost every row against the raw vendor
# files and report missing files as mismatches, so they run only where
# data/raw/ exists; their headline t is rechecked by tools/effect_lines.py.
RECOMPUTE_RAW := research/001-slope-duration-switch \
                 research/002-slope-duration-switch-r \
                 research/007-bond-carry-tilt-long-history \
                 research/008-bond-value-tilt-long-history

.PHONY: help venv test lint coverage reproduce reproduce-raw charts tearsheets dashboard clean

help:
	@sed -n '3,19p' $(firstword $(MAKEFILE_LIST))

venv:
	python3 -m venv .venv
	.venv/bin/python -m pip install --quiet --upgrade pip
	@set -e; for d in $(SUITES); do .venv/bin/python -m pip install --quiet -r $$d/requirements.txt; done
	.venv/bin/python -m pip install --quiet -r requirements-dev.txt

test:
	@set -e; for d in $(SUITES); do echo "== $$d"; (cd $$d && $(PYTHON) -m pytest -q); done

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy

coverage:
	cd qune_research && $(PYTHON) -m pytest -q --cov=qune_research --cov-config=../pyproject.toml --cov-report=term-missing

# Each script prints one row per published statistic and a summary line.  The
# target shows the summary and the mismatch list; run a script directly for the
# full table.  The target fails only when a script did not run to its summary.
reproduce:
	@set -e; failed=0; \
	for d in $(RECOMPUTE); do \
	  echo "== $$d: the reviewer's recomputation from the committed result files"; \
	  out=$$(cd $$d && $(PYTHON) -I review_recompute.py 2>&1) && code=0 || code=$$?; \
	  if printf '%s\n' "$$out" | grep -q -E '^(Rows: [0-9]+|[0-9]+ rows:)'; then \
	    printf '%s\n' "$$out" | grep -A 40 -E '^(Rows: [0-9]+|[0-9]+ rows:)' | grep -v '^| ' ; \
	    echo "   (script exit status $$code; compare with REVIEW.md)"; \
	  else \
	    printf '%s\n' "$$out" | tail -n 5; echo "   FAILED: no summary line (exit status $$code)"; failed=1; \
	  fi; \
	done; \
	echo "== tools/effect_lines.py: Studies 006-008 headline t from the committed monthly files"; \
	el=$$($(PYTHON) -I tools/effect_lines.py 2>&1) || { echo "$$el" | tail -n 3; echo "   FAILED: effect_lines.py"; failed=1; }; \
	printf '%s\n' "$$el" | sed -n '4,7p'; \
	exit $$failed

reproduce-raw:
	@set -e; for d in $(RECOMPUTE_RAW); do \
	  echo "== $$d"; \
	  if [ ! -d $$d/data/raw ]; then echo "   skipped: $$d/data/raw/ is absent (raw vendor files are not redistributed)"; continue; fi; \
	  (cd $$d && $(PYTHON) -I review_recompute.py | tail -n 12); \
	done

charts:
	@set -e; for d in $(STUDIES); do echo "== $$d/charts"; if [ ! -f $$d/charts/make_charts.py ]; then echo "   none yet"; continue; fi; (cd $$d/charts && $(PYTHON) make_charts.py); done
	@git diff --stat -- '*/charts/*' || true

tearsheets:
	$(PYTHON) tools/make_tearsheets.py
	@git diff --stat -- tearsheets || true

dashboard:
	$(PYTHON) tools/make_paper_dashboard.py
	@git diff --stat -- dashboard || true

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -f qune_research/.coverage
