.PHONY: setup verify
setup:
	python -m pip install -r requirements.txt
verify:
	python derive_alpha.py
