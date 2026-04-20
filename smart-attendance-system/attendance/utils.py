import csv
import io
import json
from datetime import datetime


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_iso():
    return datetime.now().strftime("%Y-%m-%d")


def to_json(data):
    return json.dumps(data, ensure_ascii=True)


def from_json(data, default=None):
    if not data:
        return default if default is not None else {}
    return json.loads(data)


def rows_to_csv(rows, headers):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return output.getvalue().encode("utf-8")
