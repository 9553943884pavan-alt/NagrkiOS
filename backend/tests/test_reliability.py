"""Offline regression checks for storage reconciliation reliability."""

import pytest

from app import object_storage


def test_private_listing_uses_each_page_once(monkeypatch):
    first = 'a' * 24 + '.png'
    second = 'b' * 24 + '.webp'

    class Client:
        def list_objects_v2(self, **kwargs):
            if 'ContinuationToken' not in kwargs:
                return {'IsTruncated': True, 'NextContinuationToken': 'page-2',
                        'Contents': [{'Key': first}]}
            assert kwargs['ContinuationToken'] == 'page-2'
            return {'IsTruncated': False, 'Contents': [{'Key': second}]}

    monkeypatch.setenv('OBJECT_STORAGE_BUCKET', 'synthetic-private-bucket')
    monkeypatch.setattr(object_storage, '_client', lambda: Client())
    assert object_storage.list_attachment_keys() == {first, second}


def test_private_listing_rejects_repeated_page_token(monkeypatch):
    calls = 0

    class Client:
        def list_objects_v2(self, **kwargs):
            nonlocal calls
            calls += 1
            assert calls <= 2, 'Listing repeated the same page indefinitely'
            return {'IsTruncated': True, 'NextContinuationToken': 'same-token',
                    'Contents': [{'Key': 'a' * 24 + '.png'}]}

    monkeypatch.setenv('OBJECT_STORAGE_BUCKET', 'synthetic-private-bucket')
    monkeypatch.setattr(object_storage, '_client', lambda: Client())
    with pytest.raises(RuntimeError, match='Repeated private object listing token'):
        object_storage.list_attachment_keys()
    assert calls == 2
