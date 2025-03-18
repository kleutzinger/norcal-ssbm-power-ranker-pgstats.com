#!/bin/sh
set -e
set -x

echo 'disabled run.sh'
exit 0

python src/scrape.py "$@"
python src/parse.py
