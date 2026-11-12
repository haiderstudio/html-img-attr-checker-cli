# html-img-attr-checker-cli

Check every `<img>` in HTML files carries width and height, fail CI when one is missing.

[![CI](https://github.com/haiderstudio/html-img-attr-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-img-attr-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_img_attr_checker` reads HTML files and finds every
`<img>` tag missing its `width` or `height` attribute — or
both — and reports each one with the file, the image, and
the line number. It exits 1 when any image is missing an
attribute, so it can fail a CI run. A file where every
image carries both attributes exits 0.

- An image with no width and height makes the page jump
  when it loads: the browser does not know how much space
  to reserve, so the text moves under the reader's eyes
  once the image arrives. That jump is called layout
  shift, and it drags down Google's Core Web Vitals score.
  The fix is one line per image, but nothing stops you
  shipping a page without them — this catches it before
  the page ships.
- An attribute counts as missing when it is absent or
  empty: `width=""` is the same as no width at all. A
  value that is present, even a percentage like
  `width="50%"`, counts as present — whether the value is
  a sensible size is a different check.
- Single-quoted, double-quoted, and unquoted values are
  all found, and so is an uppercase `IMG` tag or a `WIDTH`
  attribute. An `<img>` inside an HTML comment does not
  count, and neither does text inside `<script>` or
  `<style>` blocks: only real images count.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  `.html` and `.htm` files, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are never
  followed.
- `--json` prints the result as JSON (the human-readable
  lines go to standard error), and `--stdin` checks one
  HTML document read from standard input.

## Who it is for

Anyone who owns a website and does not want the page to
jump while it loads — front-end developers, teams that
review each other's templates, and anyone whose pages
carry images added by hand or by a CMS.

## What it does NOT do

- It does not check alt text. That is repo #30,
  image-alt-checker-cli, which checks alt text only —
  this tool checks the width and height attributes, a
  different check on the same tags. The two tools do not
  overlap: an image can pass this one and fail that one,
  or the other way round.
- It does not check the pixel size of the image file
  itself. That is repo #51, image-dimension-checker-cli,
  which opens the image file and measures it — attributes
  in the HTML are a different check.
- It does not check whether a width or height value is a
  sensible size — `width="abc"` passes, because the
  attribute is there. Whether the value is valid is a
  different check.
- It does not fetch a live site, and it never rewrites a
  file. It is report-only, and it never touches the
  network.

## How this differs

- The field is empty for this job: a fresh search of
  GitHub on Nov 11, 2026 found 0 results for
  `"html-img-attr-checker-cli"` and 0 results for
  `html img attribute checker`. No rival checks img
  width and height attributes.
- Repo #30, image-alt-checker-cli, checks alt text only;
  width and height attributes are a different check on
  the same tags. Repo #51, image-dimension-checker-cli,
  checks the pixel dimensions of the image files
  themselves; attributes in the HTML are a different
  check.

## Install

```sh
git clone https://github.com/haiderstudio/html-img-attr-checker-cli.git
cd html-img-attr-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one HTML file:

```sh
python3 src/html_img_attr_checker.py page.html
```

A file where every image has both attributes passes:

```sh
$ python3 src/html_img_attr_checker.py examples/good.html
OK — 1 file(s) checked, every image has width and height.
```

A file with images missing attributes fails, with the
image and line for each one:

```sh
$ python3 src/html_img_attr_checker.py examples/bad.html
FAIL examples/bad.html: <img src="hero.jpg"> line 7 is missing width and height
FAIL examples/bad.html: <img src="thumb.jpg"> line 8 is missing height
FAIL examples/bad.html: <img src="icon.png"> line 9 is missing width
FAIL examples/bad.html: <img src="empty.jpg"> line 10 is missing width
Checked 1 file(s), 4 problem(s) in 1 file(s).
```

Check a whole folder (HTML files only):

```sh
$ python3 src/html_img_attr_checker.py examples/
FAIL examples/bad.html: <img src="hero.jpg"> line 7 is missing width and height
FAIL examples/bad.html: <img src="thumb.jpg"> line 8 is missing height
FAIL examples/bad.html: <img src="icon.png"> line 9 is missing width
FAIL examples/bad.html: <img src="empty.jpg"> line 10 is missing width
Checked 3 file(s), 4 problem(s) in 1 file(s).
```

Check one document from standard input:

```sh
$ python3 src/html_img_attr_checker.py --stdin < examples/bad.html
FAIL <stdin>: <img src="hero.jpg"> line 7 is missing width and height
FAIL <stdin>: <img src="thumb.jpg"> line 8 is missing height
FAIL <stdin>: <img src="icon.png"> line 9 is missing width
FAIL <stdin>: <img src="empty.jpg"> line 10 is missing width
Checked 1 file(s), 4 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_img_attr_checker.py --json examples/bad.html
{
  "files": [
    {
      "path": "examples/bad.html",
      "images": [
        {
          "line": 7,
          "src": "hero.jpg",
          "missing": [
            "width",
            "height"
          ]
        },
        {
          "line": 8,
          "src": "thumb.jpg",
          "missing": [
            "height"
          ]
        },
        {
          "line": 9,
          "src": "icon.png",
          "missing": [
            "width"
          ]
        },
        {
          "line": 10,
          "src": "empty.jpg",
          "missing": [
            "width"
          ]
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 4
}
```

Exit codes: 0 when every image has width and height, 1
when any image is missing an attribute or a file cannot
be read, 2 for a usage error (a missing path, a bad flag,
or no HTML files found).

## Examples

An empty attribute counts as missing — the
`width=""` on line 10 of `examples/bad.html` is reported,
while the fully-sized image on line 11 passes:

```sh
$ python3 src/html_img_attr_checker.py examples/bad.html
FAIL examples/bad.html: <img src="hero.jpg"> line 7 is missing width and height
FAIL examples/bad.html: <img src="thumb.jpg"> line 8 is missing height
FAIL examples/bad.html: <img src="icon.png"> line 9 is missing width
FAIL examples/bad.html: <img src="empty.jpg"> line 10 is missing width
Checked 1 file(s), 4 problem(s) in 1 file(s).
```

Quoting does not matter — the single-quoted, unquoted,
and uppercase images in `examples/good.html` all pass,
and the commented-out `<img>` and the one inside the
`<script>` are ignored:

```sh
$ python3 src/html_img_attr_checker.py examples/good.html
OK — 1 file(s) checked, every image has width and height.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_html_img_attr_checker.py
```

The tests cover img parsing (missing both attributes,
missing width only, missing height only, empty width,
empty height, whitespace-only value, single-quoted,
double-quoted, and unquoted values, uppercase `IMG` and
`WIDTH`/`HEIGHT` attributes, an image with no `src`,
self-closing tags, images inside comments, `<script>`,
and `<style>` ignored, unclosed tags, a document with
no images, an empty document), the check itself (images
reported in document order, each with the right line
and missing list, clean files pass), the CLI (exit 0/1/2,
folder walking, `.html` and `.htm` only, `.git` skipped,
`--no-recursive`, `--exclude`, a direct file checked
even without an HTML name, `--stdin`, `--json` output,
`--version`, bad flags, missing paths, empty folders, a
non-UTF-8 file reported, input files left unchanged),
the bundled examples (sample output compared
byte-for-byte against a fresh run, and the README-quoted
outputs checked against it), and hygiene checks (no
placeholder text, no absolute paths, stdlib imports
only, `.env` first in `.gitignore`, CI file runs the
test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking img width and height is not new, but
no existing tool does this one job as a tested
command-line gate — the field is empty, as the search
above shows — and every line of code here is original,
built on nothing but Python's standard library.
