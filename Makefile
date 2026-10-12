PYTHON ?= python3
APP = main:app

setup:
	$(PYTHON) -m pip install -r requirements.txt

build-data:
	$(PYTHON) scripts/build_dataset.py

run:
	$(PYTHON) -m uvicorn $(APP) --reload --host 0.0.0.0 --port 8000

test:
	$(PYTHON) -m pytest -q

eval:
	$(PYTHON) eval/make_test_set.py
	$(PYTHON) eval/correlate.py
	$(PYTHON) eval/adversarial.py
	$(PYTHON) eval/baseline_tfidf.py
