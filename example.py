import argparse
import sys

from cli import ClientError, DEFAULT_URL, EditorClient, output_path, read_file, save_bytes, write_new

OPERATIONS = [
    {"action": "items.xp", "args": {"value": 1000}},
    {"action": "cats.guide", "args": {"select": [{"kind": "ids", "ids": [0]}], "collected": True}},
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Edit a save through the BCSFE API and write a new output file.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--url", default=None, help="API origin; defaults to BCSFE_API_URL or " + DEFAULT_URL)
    parser.add_argument("--country", choices=("kr", "en", "jp", "tw"), default="kr")
    args = parser.parse_args(argv)
    try:
        target = output_path(args.output, [args.input])
        original = read_file(args.input)
        client = EditorClient(args.url)
        result = client.edit(original, OPERATIONS, args.country)
        edited = save_bytes(result)
        write_new(target, edited)
        print(f"Saved {len(edited)} bytes to a new output file.")
        return 0
    except (ClientError, OSError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
