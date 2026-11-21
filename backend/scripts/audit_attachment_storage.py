"""Read-only, aggregate reconciliation of attachment metadata and private objects.

Run only against a verified disposable branch during integration testing. This
script never prints object keys, user details or attachment names, and never
deletes source files or cloud objects.
"""
from __future__ import annotations

import json

from app import object_storage
from app.db import connect


def audit() -> dict[str, int]:
    object_storage.validate_config()
    if not object_storage.configured():
        raise RuntimeError('Private object storage is not configured')
    with connect() as db:
        metadata_keys = {row['filename'] for row in db.execute('SELECT filename FROM attachments')}
    cloud_keys = object_storage.list_attachment_keys()
    return {'metadata_rows': len(metadata_keys), 'private_objects': len(cloud_keys),
            'objects_without_metadata': len(cloud_keys - metadata_keys),
            'metadata_without_cloud_object': len(metadata_keys - cloud_keys)}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
