#!/usr/bin/env python3
"""The 3AM Fridge Text — publish the fridge's one-line text.

A smart fridge has been awake all night watching its owner come
back for "just one bite" again and again. At 3:04 AM it finally
texts the owner: the leftovers have filed a formal complaint, and
the fridge is forwarding that complaint to the owner's future
self. The line itself lives in ``entry.txt`` beside this script;
this script never invents, edits, or re-types it.

What the script does, in order:

1. Reads ``entry.txt`` as raw bytes, exactly as stored.
2. Decodes those bytes as UTF-8 and measures the message the way
   the bounty gate measures it: Unicode code points, not bytes,
   one single line, between 1 and 140 characters, and more than
   blank space.
3. Copies the raw bytes — trailing newline and all — into
   ``entry.txt`` inside the output directory, then reads the copy
   back and refuses to report success unless every byte matches.
   A byte-order mark at the start of the file is rejected outright:
   it would decode to an invisible extra character and the
   published bytes would no longer be the line the gate measured.

The destination defaults to ``/output``. Pass ``--output-dir`` to
choose another folder, or set ``MAKEFUN_OUTPUT_DIR``. Use
``--verify-only`` to check the line without writing anything, and
``--quiet`` to stay silent on success. Only the standard library
is used; there is no network access, no clock, and no randomness,
so repeated runs are identical.

Usage:
    python3 main.py [--output-dir DIR] [--max-chars N]
                    [--verify-only] [--quiet] [--show]

Exit status is 0 on success, 1 when the entry fails the gate or
the output cannot be written, and 2 when an argument is bad.
"""

import argparse
import os
import sys
from pathlib import Path

LIMIT = 140
FALLBACK_DIR = "/output"
SOURCE_NAME = "entry.txt"


class GateFailure(Exception):
    """Raised when the stored line does not satisfy the gate."""


def source_file():
    """Path of the entry file shipped next to this script."""
    return Path(__file__).resolve().parent / SOURCE_NAME


def read_source():
    """Return the entry file's raw bytes, or raise GateFailure."""
    try:
        return source_file().read_bytes()
    except FileNotFoundError:
        raise GateFailure("entry.txt is missing next to main.py")
    except OSError as problem:
        raise GateFailure("entry.txt could not be read: %s" % problem)


def split_trailing_newline(text):
    """Split off one trailing newline; return (body, had_newline)."""
    if text.endswith("\n"):
        return text[:-1], True
    return text, False


def check_line(text, limit):
    """Validate the decoded line and return (body, had_newline).

    The gate counts characters as Unicode code points. A line that
    is empty, blank, split over several lines, padded with spaces,
    holding a control character, or longer than ``limit`` fails.
    """
    body, had_newline = split_trailing_newline(text)
    if body == "" or body.isspace():
        raise GateFailure("entry is empty or only white space")
    if "\n" in body or "\r" in body:
        raise GateFailure("entry must be exactly one line")
    if body.strip() != body:
        raise GateFailure("entry has leading or trailing white space")
    for char in body:
        if ord(char) < 0x20:
            raise GateFailure("entry contains a control character")
    if len(body) > limit:
        raise GateFailure(
            "entry is %d characters, over the %d limit" % (len(body), limit)
        )
    return body, had_newline


def decode_and_check(raw, limit):
    """Decode raw bytes as UTF-8 and run the gate over the result."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raise GateFailure("entry.txt starts with a UTF-8 byte-order mark")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as problem:
        raise GateFailure("entry.txt is not valid UTF-8: %s" % problem)
    return check_line(text, limit)


def describe(body, raw, had_newline):
    """One human-readable line describing the validated entry."""
    words = len(body.split())
    tail = "with" if had_newline else "without"
    return "%d characters, %d words, %d bytes, %s trailing newline" % (
        len(body),
        words,
        len(raw),
        tail,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Validate and publish the 3AM Fridge Text entry.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=None,
        help="write entry.txt into DIR (default: $MAKEFUN_OUTPUT_DIR or /output)",
    )
    parser.add_argument(
        "--max-chars",
        metavar="N",
        type=int,
        default=LIMIT,
        help="character limit to check against (default: 140)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="only validate the entry; write nothing",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print nothing on success",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="also print the entry line itself on success",
    )
    return parser


def pick_output_dir(args):
    """Resolve the output directory from flag, env, then default."""
    chosen = args.output_dir or os.environ.get("MAKEFUN_OUTPUT_DIR") or FALLBACK_DIR
    folder = Path(chosen)
    if folder.exists() and not folder.is_dir():
        raise GateFailure("output path is not a directory: %s" % folder)
    if folder.resolve() == Path(__file__).resolve().parent:
        raise GateFailure("output directory must not be the repository root")
    return folder


def write_verbatim(raw, folder):
    """Write raw bytes to folder/entry.txt and prove the copy matches."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / SOURCE_NAME
    target.write_bytes(raw)
    if target.read_bytes() != raw:
        raise GateFailure("published entry does not match entry.txt")
    return target


def report_error(message):
    print(message, file=sys.stderr)
    return 1


def run(argv=None):
    args = build_parser().parse_args(argv)
    if args.max_chars < 1:
        print("--max-chars must be at least 1", file=sys.stderr)
        return 2
    try:
        raw = read_source()
        body, had_newline = decode_and_check(raw, args.max_chars)
    except GateFailure as problem:
        return report_error("Invalid: %s" % problem)
    summary = describe(body, raw, had_newline)
    if len(body) > args.max_chars - 10:
        print(
            "Note: entry is %d characters, within 10 of the %d limit"
            % (len(body), args.max_chars),
            file=sys.stderr,
        )
    if args.verify_only:
        if not args.quiet:
            print("Valid: %s" % summary)
        if args.show:
            print(body)
        return 0
    try:
        folder = pick_output_dir(args)
        target = write_verbatim(raw, folder)
    except GateFailure as problem:
        return report_error("Invalid: %s" % problem)
    except OSError as problem:
        return report_error("Cannot write output: %s" % problem)
    if not args.quiet:
        print("Wrote %s to %s" % (summary, target))
    if args.show:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(run())
