"""Preview or explicitly remove a contact's current stored data; never unlink exports."""
import argparse
import json
from pathlib import Path
import sqlite3

from .privacy import Privacy
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--contact', required=True)
    parser.add_argument('--apply-plan', metavar='SHA256', help='Exact plan hash from a fresh preview')
    parser.add_argument('--confirm-delete', action='store_true',
                        help='Confirm irreversible removal of the reviewed current database records')
    args = parser.parse_args(argv)
    if args.confirm_delete and args.apply_plan is None:
        parser.error('--confirm-delete requires --apply-plan; preview first')
    store = None
    try:
        # mode=rw refuses missing paths without creating a database or migrating schema.
        store = Store(str(args.db), readonly=args.apply_plan is None, create=False)
        privacy = Privacy(store)
        if args.apply_plan is None:
            result = privacy.preview(owner=args.owner, contact=args.contact)
        else:
            result = privacy.apply(owner=args.owner, contact=args.contact,
                expected_plan_sha256=args.apply_plan, confirm=args.confirm_delete)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    except sqlite3.Error:
        parser.error('Local database operation failed; use an existing supported store')
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    main()
