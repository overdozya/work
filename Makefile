PYTHON ?= python3

.PHONY: run demo check browser-check
run:
	$(PYTHON) -m atelier.server

demo:
	ATELIER_MODE=demo $(PYTHON) -m atelier.server

check:
	$(PYTHON) -m unittest discover -s tests -v
	node --check web/app.js

browser-check:
	node tests/browser_smoke.cjs
