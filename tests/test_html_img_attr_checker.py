#!/usr/bin/env python3
"""Tests for html_img_attr_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_img_attr_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


class TestFindBadImages(unittest.TestCase):
    def test_image_with_both_attributes_passes(self):
        html = '<img src="a.jpg" width="100" height="50" alt="A">'
        self.assertEqual(checker.find_bad_images(html), [])

    def test_missing_both_attributes(self):
        html = '<img src="a.jpg" alt="A">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 1)
        self.assertEqual(got[0]["src"], "a.jpg")
        self.assertEqual(got[0]["missing"], ["width", "height"])

    def test_missing_width_only(self):
        html = '<img src="a.jpg" height="50">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["width"])

    def test_missing_height_only(self):
        html = '<img src="a.jpg" width="100">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["height"])

    def test_empty_width_counts_as_missing(self):
        html = '<img src="a.jpg" width="" height="50">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["width"])

    def test_empty_height_counts_as_missing(self):
        html = '<img src="a.jpg" width="100" height="">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["height"])

    def test_whitespace_only_value_counts_as_missing(self):
        html = '<img src="a.jpg" width="  " height="50">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["width"])

    def test_percentage_value_counts_as_present(self):
        html = '<img src="a.jpg" width="50%" height="50%">'
        self.assertEqual(checker.find_bad_images(html), [])

    def test_single_quoted_values_found(self):
        html = "<img src='a.jpg' width='100' height='50'>"
        self.assertEqual(checker.find_bad_images(html), [])

    def test_unquoted_values_found(self):
        html = '<img src=a.jpg width=100 height=50>'
        self.assertEqual(checker.find_bad_images(html), [])

    def test_unquoted_missing_found(self):
        html = '<img src=a.jpg width=100>'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["height"])

    def test_uppercase_img_tag_and_attributes(self):
        html = '<IMG SRC="a.jpg" WIDTH="100" HEIGHT="50">'
        self.assertEqual(checker.find_bad_images(html), [])

    def test_uppercase_missing_found(self):
        html = '<IMG SRC="a.jpg" WIDTH="100">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["height"])

    def test_image_with_no_src_still_checked(self):
        html = '<img width="100">'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0]["src"])
        self.assertEqual(got[0]["missing"], ["height"])

    def test_self_closing_tag_checked(self):
        html = '<img src="a.jpg" />'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["missing"], ["width", "height"])

    def test_images_reported_in_document_order_with_lines(self):
        html = ('<img src="a.jpg">\n'
                '<p>text</p>\n'
                '<img src="b.jpg" width="100">\n'
                '<img src="c.jpg" width="100" height="50">\n'
                '<img src="d.jpg" height="50">')
        got = checker.find_bad_images(html)
        self.assertEqual(
            [(g["src"], g["line"], g["missing"]) for g in got],
            [("a.jpg", 1, ["width", "height"]),
             ("b.jpg", 3, ["height"]),
             ("d.jpg", 5, ["width"])])

    def test_non_img_tags_ignored(self):
        html = '<div width="100"></div><video src="v.mp4"></video>'
        self.assertEqual(checker.find_bad_images(html), [])

    def test_img_inside_comment_ignored(self):
        html = ('<img src="a.jpg" width="100" height="50">\n'
                '<!-- <img src="b.jpg"> not a real image -->')
        self.assertEqual(checker.find_bad_images(html), [])

    def test_img_inside_script_ignored(self):
        html = ('<script>\n'
                'var s = \'<img src="fake.jpg">\';\n</script>\n'
                '<img src="a.jpg" width="100" height="50">')
        self.assertEqual(checker.find_bad_images(html), [])

    def test_img_inside_style_ignored(self):
        html = ('<style>\nimg { width: 100px; }\n</style>\n'
                '<img src="a.jpg" width="100" height="50">')
        self.assertEqual(checker.find_bad_images(html), [])

    def test_unclosed_tags_still_parsed(self):
        html = '<img src="a.jpg">\n<p>text'
        got = checker.find_bad_images(html)
        self.assertEqual(len(got), 1)

    def test_empty_document(self):
        self.assertEqual(checker.find_bad_images(""), [])

    def test_no_images_at_all(self):
        html = '<div><p>plain text</p></div>'
        self.assertEqual(checker.find_bad_images(html), [])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<img src="a.jpg" width="100" height="50">')
            bad, err = checker.check_file(path)
            self.assertEqual((bad, err), ([], None))

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<img src="a.jpg">')
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(len(bad), 1)

    def test_missing_file_reports_error(self):
        bad, err = checker.check_file("/nonexistent/page.html")
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<img src="a\xff.jpg">')
            bad, err = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertEqual(err, "not valid UTF-8")

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = '<img src="a.jpg">'
            path = write(tmp, "bad.html", text)
            checker.check_file(path)
            self.assertEqual(Path(path).read_text(), text)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", '<img src="a.jpg">')
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            b = write(tmp, "sub/b.htm", "")
            write(tmp, "c.md", "")
            write(tmp, "d.txt", "")
            got = checker.collect_files([tmp])
            self.assertEqual(got, sorted([a, b]))

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.html", "")
            a = write(tmp, "a.html", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "sub/b.html", "")
            self.assertEqual(
                checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "skip.html", "")
            got = checker.collect_files([tmp], exclude=["skip.html"])
            self.assertEqual(got, [a])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            checker.collect_files(["/nonexistent/path"])

    def test_duplicates_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", "")
            self.assertEqual(
                checker.collect_files([path, path]), [path])


class TestRun(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<img src="a.jpg" width="100" height="50">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn(
                "OK — 1 file(s) checked, every image has width and height.",
                out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<img src="a.jpg">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            # CWD-robust: assert on the file name and message, never
            # on the absolute path the CLI echoes.
            self.assertIn("bad.html", out)
            self.assertIn('<img src="a.jpg"> line 1 is missing '
                          "width and height", out)
            self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_missing_width_only_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<img src="a.jpg" height="50">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn('<img src="a.jpg"> line 1 is missing width',
                          out)

    def test_image_without_src_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<img width="100">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn("<img> line 1 is missing height", out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.html",
                  '<img src="a.jpg" width="100" height="50">')
            write(tmp, "bad.html", '<img src="a.jpg">')
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<img src="a.jpg">\n<img src="b.jpg" width="1">')
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["problems"], 2)
            self.assertEqual(
                os.path.basename(data["files"][0]["path"]), "bad.html")
            self.assertEqual(data["files"][0]["images"][0]["src"], "a.jpg")
            self.assertEqual(data["files"][0]["images"][0]["missing"],
                             ["width", "height"])
            self.assertEqual(data["files"][0]["images"][1]["missing"],
                             ["height"])
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("")
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn(
            "OK — 1 file(s) checked, every image has width and height.",
            out)

    def test_stdin_dirty_via_main(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO('<img src="a.jpg">')
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            'FAIL <stdin>: <img src="a.jpg"> line 1 is missing '
            "width and height", out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.html"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("at least one HTML file", err)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no HTML files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_img_attr_checker 1.0.0", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<img src="a\xff.jpg">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/html_img_attr_checker.py",
             "examples/good.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/html_img_attr_checker.py",
             "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_img_attr_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 4 problem(s) in 1 file(s).",
                      folder.stdout)
        self.assertIn("Checked 3 file(s), 4 problem(s) in 1 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/html_img_attr_checker.py",
             "--json", "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_secrets(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore").lower()
            for marker in ("api_key", "api-key", "password", "secret=",
                           "token="):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        src = REPO / "src/html_img_attr_checker.py"
        tree = ast.parse(src.read_text())
        stdlib = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported - stdlib, imported)
        self.assertNotIn("yaml", imported)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_html_img_attr_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)


if __name__ == "__main__":
    unittest.main()
