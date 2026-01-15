#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests"]
# ///
"""
Zotero Collection Selector

List and select Zotero libraries/collections via the export-org extension API.
Use this to set the target collection before running zotero_saver.py.

Usage:
    uv run zotero_collection.py              # Interactive selection
    uv run zotero_collection.py --current    # Show current selection
    uv run zotero_collection.py --list       # List all collections
    uv run zotero_collection.py --select KEY # Select collection by key
"""

import argparse
import json
import shutil
import subprocess
import sys

import requests

DEFAULT_ZOTERO_PORT = 23119
BASE_PATH = "/export-org"


def get_api_url(port: int, endpoint: str) -> str:
    return f"http://127.0.0.1:{port}{BASE_PATH}{endpoint}"


def get_current_collection(port: int) -> dict | None:
    """Get the currently selected library/collection."""
    try:
        r = requests.get(get_api_url(port, "/collection/current"), timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def list_collections(port: int) -> dict | None:
    """Get hierarchical list of all libraries and collections."""
    try:
        r = requests.get(get_api_url(port, "/collections/list"), timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def select_collection(port: int, library_id: int, collection_key: str | None) -> dict | None:
    """Select a library or collection in Zotero's UI."""
    try:
        r = requests.post(
            get_api_url(port, "/collection/select"),
            json={"libraryID": library_id, "collectionKey": collection_key},
            timeout=5
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def print_tree(collections: list, prefix: str = "", start_idx: int = 1) -> tuple[list, int]:
    """Print collection tree and return flat list for selection.

    Returns (items, next_idx) where items is flat list and next_idx is the next available index.
    """
    items = []
    idx = start_idx

    for i, c in enumerate(collections):
        is_last = i == len(collections) - 1
        branch = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

        items.append(c)
        print(f"{prefix}{branch}[{idx}] {c['name']}")
        idx += 1

        if c.get("children"):
            child_items, idx = print_tree(c["children"], prefix + child_prefix, idx)
            items.extend(child_items)

    return items, idx


def build_flat_list(libraries: list) -> list:
    """Build flat list of all selectable items from library data."""
    all_items = []

    def add_collections(collections: list, lib_id: int, lib_name: str, depth: int = 0):
        for c in collections:
            indent = "  " * depth
            all_items.append({
                "type": "collection",
                "id": lib_id,
                "name": c["name"],
                "key": c["key"],
                "display": f"{lib_name} > {indent}{c['name']}"
            })
            if c.get("children"):
                add_collections(c["children"], lib_id, lib_name, depth + 1)

    for lib in libraries:
        # Add library root
        all_items.append({
            "type": "library",
            "id": lib["id"],
            "name": lib["name"],
            "key": None,
            "display": f"{lib['name']} (root)"
        })
        # Add collections
        if lib.get("collections"):
            add_collections(lib["collections"], lib["id"], lib["name"])

    return all_items


def fuzzy_select(items: list) -> dict | None:
    """Use fzf for fuzzy selection if available."""
    fzf_path = shutil.which("fzf")
    if not fzf_path:
        return None

    # Build input for fzf: "index:display_name"
    fzf_input = "\n".join(f"{i}:{item['display']}" for i, item in enumerate(items))

    try:
        result = subprocess.run(
            [fzf_path, "--height=40%", "--reverse", "--prompt=Collection> ",
             "--with-nth=2..", "--delimiter=:"],
            input=fzf_input,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            idx = int(result.stdout.strip().split(":")[0])
            return items[idx]
    except Exception:
        pass

    return None


def numbered_select(items: list, libraries: list) -> dict | None:
    """Fallback numbered selection when fzf is not available."""
    next_idx = 1

    for lib in libraries:
        print(f"[{next_idx}] {lib['name']} (Library root)")
        next_idx += 1

        if lib.get("collections"):
            _, next_idx = print_tree(lib["collections"], prefix="    ", start_idx=next_idx)

        print()

    try:
        choice = input("Select number (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return None

        idx = int(choice) - 1
        if idx < 0 or idx >= len(items):
            print("Invalid selection.")
            return None

        return items[idx]

    except (ValueError, EOFError):
        return None


def interactive_select(port: int, use_fzf: bool = True) -> bool:
    """Interactive collection selection."""
    data = list_collections(port)
    if not data:
        return False

    libraries = data.get("libraries", [])
    if not libraries:
        print("No libraries found.")
        return False

    # Build flat list of all selectable items
    all_items = build_flat_list(libraries)

    # Try fzf first, fall back to numbered list
    selected = None
    if use_fzf:
        selected = fuzzy_select(all_items)

    if selected is None and not use_fzf:
        selected = numbered_select(all_items, libraries)
    elif selected is None:
        # fzf not available or cancelled, try numbered
        print("(fzf not found or cancelled, using numbered list)\n")
        selected = numbered_select(all_items, libraries)

    if selected is None:
        return False

    result = select_collection(port, selected["id"], selected["key"])

    if result and result.get("success"):
        if selected["key"]:
            print(f"Selected: {selected['name']} in library {selected['id']}")
        else:
            print(f"Selected: {selected['name']} (library root)")
        return True
    else:
        print(f"Failed to select: {result.get('error', 'Unknown error')}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="List and select Zotero collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive selection
  %(prog)s --current                # Show current selection
  %(prog)s --list                   # List all collections (JSON)
  %(prog)s --list --tree            # List as tree
  %(prog)s --library 1 --select KEY # Select specific collection
  %(prog)s --library 1              # Select library root
        """
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_ZOTERO_PORT,
        help=f"Zotero port (default: {DEFAULT_ZOTERO_PORT})"
    )
    parser.add_argument(
        "--current", "-c",
        action="store_true",
        help="Show currently selected collection"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all libraries and collections"
    )
    parser.add_argument(
        "--tree", "-t",
        action="store_true",
        help="Display list as tree (with --list)"
    )
    parser.add_argument(
        "--library",
        type=int,
        metavar="ID",
        help="Library ID for selection"
    )
    parser.add_argument(
        "--select", "-s",
        metavar="KEY",
        help="Collection key to select (use with --library)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--no-fzf",
        action="store_true",
        help="Use numbered list instead of fuzzy finder"
    )

    args = parser.parse_args()

    # Show current selection
    if args.current:
        data = get_current_collection(args.port)
        if data:
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                lib_name = data.get("libraryName", "Unknown")
                coll = data.get("collection")
                if coll:
                    print(f"Library: {lib_name} (ID: {data.get('libraryID')})")
                    print(f"Collection: {coll['name']} (Key: {coll['key']})")
                else:
                    print(f"Library: {lib_name} (ID: {data.get('libraryID')})")
                    print("Collection: (library root)")
        return 0 if data else 1

    # List all collections
    if args.list:
        data = list_collections(args.port)
        if data:
            if args.json or not args.tree:
                print(json.dumps(data, indent=2))
            else:
                for lib in data.get("libraries", []):
                    print(f"{lib['name']} (Library ID: {lib['id']})")
                    if lib.get("collections"):
                        print_tree(lib["collections"], prefix="  ")  # ignore return
                    print()
        return 0 if data else 1

    # Programmatic selection
    if args.library is not None:
        result = select_collection(args.port, args.library, args.select)
        if result:
            if args.json:
                print(json.dumps(result, indent=2))
            elif result.get("success"):
                sel = result.get("selected", {})
                if sel.get("collectionKey"):
                    print(f"Selected: {sel.get('collectionName')} (Key: {sel.get('collectionKey')})")
                else:
                    print(f"Selected: Library {sel.get('libraryID')} (root)")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
                return 1
        return 0 if result and result.get("success") else 1

    # Interactive selection (default)
    success = interactive_select(args.port, use_fzf=not args.no_fzf)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
