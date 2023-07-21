import csv
from io import StringIO
import requests


SHEET_URL = "https://docs.google.com/spreadsheets/d/1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY/export?format=csv&gid=0"


def get_csv(csv_dl) -> list:
    resp = requests.get(csv_dl)
    scsv = resp.text

    f = StringIO(scsv)
    reader = csv.reader(f, delimiter=",")
    rows = []
    for row in reader:
        rows.append(row)
        print("\t".join(row))
    return rows


def main():
    rows = get_csv(SHEET_URL)
    print(rows)


if __name__ == "__main__":
    main()
