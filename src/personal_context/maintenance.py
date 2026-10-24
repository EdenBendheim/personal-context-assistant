"""Rebuild SQLite indexes while proving that application records stay unchanged."""
import argparse
import json
from pathlib import Path
import sqlite3

from .privacy import Privacy, _hash
from .store import Store


def _integrity(connection):
    if [row[0] for row in connection.execute('PRAGMA integrity_check')] != ['ok']:
        raise ValueError('SQLite integrity check failed; rebuild was not accepted')


def _reindex(connection):
    connection.execute('REINDEX')


def rebuild_indexes(store):
    privacy = Privacy(store)
    with privacy._transaction(write=True):
        _integrity(store.connection)
        before = privacy._snapshot()
        _reindex(store.connection)
        _integrity(store.connection)
        after = privacy._snapshot()
        if before != after:
            raise ValueError('Index rebuild changed application records; rolled back')
        indexes = sum(len(list(store.connection.execute(f'PRAGMA index_list({table})')))
                      for table in before['rows'])
        return dict(version=1, indexes_rebuilt=indexes, integrity='ok',
                    store_sha256=_hash(after), application_records_unchanged=True,
                    vector_index_present=False, physical_erasure_guaranteed=False,
                    limitation='Rebuilds SQLite indexes only; no persistent vector index exists. '
                               'Does not compact files or remove exports, backups or storage remnants.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--rebuild-indexes', action='store_true', required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        store = Store(str(args.db), create=False)
        print(json.dumps(rebuild_indexes(store), indent=2))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    except sqlite3.Error:
        parser.error('Local database operation failed; use an existing supported store')
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    main()
