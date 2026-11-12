#!/usr/bin/env python3
"""Check <img> tags in HTML files carry width and height attributes.

Run: python3 src/html_img_attr_checker.py page.html
     python3 src/html_img_attr_checker.py site/
     python3 src/html_img_attr_checker.py --stdin < page.html

An image with no width and height makes the page jump when it
loads: the browser does not know how much space to reserve, so
the text moves under the reader's eyes once the image arrives.
That jump is called layout shift, and it drags down Google's
Core Web Vitals score. The fix is one line per image — a width
and a height attribute — but nothing stops you shipping a page
without them. This tool finds every <img> missing one or both
before the page ships, instead of after a reader watches the
text jump.

It reads one or more HTML files, records every <img> tag with
its line number and its width and height attributes, and
reports each image missing one or both, with the file and the
line. It exits 1 when any image is missing an attribute, so
it can fail a CI run. A file where every image carries both
attributes exits 0.

An attribute counts as missing when it is absent or empty:
width="" is the same as no width at all. A value that is
present, even a percentage like width="50%", counts as
present — whether the value is a sensible size is a
different check. Single-quoted, double-quoted, and unquoted
values are all found, and so is an uppercase IMG tag or a
WIDTH attribute. An <img> inside an HTML comment does not
count, and neither does text inside <script> or <style>
blocks: only real images count.

It never rewrites a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_EXTENSIONS = {".html", ".htm"}


class _ImgCollector(HTMLParser):
    """Collect (line, src, missing) for every <img> tag seen."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        line, _ = self.getpos()
        values = {name: value for name, value in attrs}
        missing = []
        for name in ("width", "height"):
            value = values.get(name)
            if value is None or value.strip() == "":
                missing.append(name)
        self.images.append(
            {"line": line, "src": values.get("src"), "missing": missing})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def find_bad_images(text):
    """Return a list of <img> tags missing width or height.

    Each entry is {"line": int, "src": str or None,
    "missing": ["width"] and/or ["height"]}. Entries are in
    document order. Images carrying both attributes are not
    listed.
    """
    collector = _ImgCollector()
    collector.feed(text)
    collector.close()
    return [img for img in collector.images if img["missing"]]


def check_text(text, path):
    """Check one document's text. Returns (bad images, error)."""
    try:
        return find_bad_images(text), None
    except Exception as exc:  # a malformed document must fail, not crash
        return [], "could not parse: %s" % exc


def check_file(path):
    """Check one file. Returns (bad images, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, str(path))


def _is_html_file(path):
    return Path(path).suffix.lower() in HTML_EXTENSIONS


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of HTML files to check.

    A file given directly is always checked, whatever its name. A
    folder is walked for .html/.htm files. .git folders are never
    walked, and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(root) / name
                    if not _is_html_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_problem(path, image):
    """One human-readable line for one image missing attributes."""
    if len(image["missing"]) == 2:
        what = "missing width and height"
    else:
        what = "missing %s" % image["missing"][0]
    if image["src"]:
        return 'FAIL %s: <img src="%s"> line %d is %s' % (
            path, image["src"], image["line"], what)
    return "FAIL %s: <img> line %d is %s" % (
        path, image["line"], what)


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2
    results = []
    problems = 0
    files_with_problems = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            problems += count
            files_with_problems += 1
        results.append({"path": path, "images": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "problems": problems},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for image in result["images"]:
                print(format_problem(result["path"], image))
        if problems:
            print("Checked %d file(s), %d problem(s) in %d file(s)."
                  % (len(files), problems, files_with_problems))
        else:
            print("OK — %d file(s) checked, every image has "
                  "width and height." % len(files))
    return 1 if problems else 0


def run_stdin(as_json=False):
    """Check one HTML document read from standard input."""
    text = sys.stdin.read()
    bad, error = check_text(text, "<stdin>")
    problems = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "images": bad,
                        "error": error}],
             "checked": 1, "problems": problems},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for image in bad:
            print(format_problem("<stdin>", image))
        if problems:
            print("Checked 1 file(s), %d problem(s) in 1 file(s)." % problems)
        else:
            print("OK — 1 file(s) checked, every image has "
                  "width and height.")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_img_attr_checker",
        description="Check <img> tags in HTML files carry width and "
                    "height attributes, fail CI when one is missing.")
    parser.add_argument("paths", nargs="*", help="HTML files or folders")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one HTML file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
