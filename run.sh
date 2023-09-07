set -e
set -x

python src/scrape.py "$@"
python src/parse.py
