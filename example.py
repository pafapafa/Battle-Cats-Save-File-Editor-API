"""Small authenticated v2 SDK example: bytes in, edited bytes to a NEW file.

Set EDITOR_API_KEY or TEMPLATE_API_KEY, then run:
  python example.py original.save edited.save
  python example.py --url https://battle-cats-save-file-editor-api.vercel.app original.save edited.save

Change OPERATIONS to actions returned by GET /v2/features. This example does not
receive transfer codes, create accounts, or upload a save to a game server.
"""
import argparse
import os
import sys

from cli import ClientError, DEFAULT_URL, EditorClient, output_path, read_file, save_bytes, write_new

OPERATIONS = [
    {"action": "items.xp", "args": {"value": 1000}},
    {"action": "cats.guide", "args": {"select": [{"kind": "ids", "ids": [0]}], "collected": True}},
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--country", choices=("kr", "en", "jp", "tw"), default="kr")
    args = parser.parse_args(argv)
    token = os.environ.get("EDITOR_API_KEY") or os.environ.get("TEMPLATE_API_KEY")
    try:
        target = output_path(args.output, [args.input])
        original = read_file(args.input)
        client = EditorClient(args.url, token)
        result = client.edit(original, OPERATIONS, args.country)
        edited = save_bytes(result)
        write_new(target, edited)
        print(f"Saved {len(edited)} bytes to a new output file.")
        return 0
    except (ClientError, OSError) as exc:
        message = str(exc).replace(token, "[redacted]") if token else str(exc)
        print("Error: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
