#!/bin/bash
#
# This script provides a simple, one-step way to verify the core result.

set -e

echo "--- Installing Dependencies ---"
pip install -r requirements.txt

echo "
--- Running Verification Script ---"
python derive_alpha.py
