

import csv
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS = os.path.join(BASE, "datasets", "term_1261", "sections.csv")

PROGRAMS = ["cmsc","mst", "soc", "phlo", "coma"]
COLUMNS = ["year", "term", "slot", "options", "kind", "prereqs", "track", "note"]
KINDS = ["CORE", "GE", "PE", "NSTP", "ELECTIVE"]
TERMS = ["FS", "SS", "MY"]
SKIP = ["GE", "ELECTIVE", "NSTP"]


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            return None, ["header is " + str(reader.fieldnames)]
        return list(reader), []


def check_format(rows):
    errors = []
    groups = {}
    tracks = set()
    for row in rows:
        tracks.add(row["track"])
    tracks.discard("ALL")
    if len(tracks) == 0:
        tracks.add("ALL")

    for i, row in enumerate(rows):
        line = i + 2
        if row["kind"] not in KINDS:
            errors.append("line " + str(line) + ": bad kind " + row["kind"])
        if row["term"] not in TERMS:
            errors.append("line " + str(line) + ": bad term " + row["term"])
        if not row["year"].isdigit():
            errors.append("line " + str(line) + ": bad year " + row["year"])
            continue
        prefix = "Y" + row["year"] + row["term"] + "-"
        if not row["slot"].startswith(prefix):
            errors.append("line " + str(line) + ": slot " + row["slot"] + " should start with " + prefix)
        if row["options"].strip() == "":
            errors.append("line " + str(line) + ": empty options")

    for track in sorted(tracks):
        groups = {}
        for row in rows:
            if row["track"] != "ALL" and row["track"] != track:
                continue
            key = (row["year"], row["term"])
            groups.setdefault(key, []).append(row["slot"])
        for key in sorted(groups):
            slots = groups[key]
            if len(slots) != len(set(slots)):
                errors.append("track " + track + " Y" + key[0] + key[1] + ": duplicate slot ids")
            numbers = []
            for s in slots:
                numbers.append(int(s.split("-")[1]))
            if sorted(numbers) != list(range(1, len(numbers) + 1)):
                errors.append("track " + track + " Y" + key[0] + key[1] + ": slot numbers not 1..n")
    return errors


def load_codes():
    codes = set()
    with open(SECTIONS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            codes.add(row["course_code"])
    return codes


def check_coverage(rows, codes):
    found = []
    missing = []
    for row in rows:
        if row["kind"] == "PE":
            continue
        options = row["options"].split("|")
        for o in options:
            o = o.strip()
            if o in SKIP:
                continue
            if o in codes:
                found.append(o)
            else:
                missing.append(o)
    return sorted(set(found)), sorted(set(missing))


def main():
    codes = load_codes()
    bad = False
    all_missing = set()
    for prog in PROGRAMS:
        path = os.path.join(BASE, "curriculum_" + prog + ".csv")
        print("=== " + prog.upper() + "  (" + path + ")")
        if not os.path.exists(path):
            print("  FILE NOT FOUND")
            bad = True
            continue
        rows, errors = load_rows(path)
        if rows is not None:
            errors = errors + check_format(rows)
        if len(errors) > 0:
            bad = True
            for e in errors:
                print("  ERROR: " + e)
            continue
        found, missing = check_coverage(rows, codes)
        print("  format OK, " + str(len(rows)) + " rows")
        print("  codes found in sections.csv: " + str(len(found)))
        print("  codes NOT in sections.csv:   " + str(len(missing)))
        if len(missing) > 0:
            print("    " + ", ".join(missing))
        for m in missing:
            all_missing.add(m.split()[0])

    print()
    print("Subjects still to scrape/build: " + ", ".join(sorted(all_missing)))
    if bad:
        sys.exit(1)


main()