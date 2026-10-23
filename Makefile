PY ?= python3
export PYTHONPATH := src

.PHONY: install test demo pipeline dashboard docs clean

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

# Tudo de ponta a ponta com dados sintéticos (apaga data/ antes)
demo: pipeline docs

pipeline:
	$(PY) -m eletrodiag.pipeline.run --fresh

dashboard:
	$(PY) -m eletrodiag.pipeline.run --steps dashboard

docs:
	$(PY) -m eletrodiag.docs.gen_dictionary
	$(PY) -m eletrodiag.synth.sensitivity

clean:
	rm -rf data/bronze data/silver data/gold data/warehouse data/_meta app/build bi/dashboard/build .pytest_cache
