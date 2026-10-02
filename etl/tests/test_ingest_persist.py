"""Closing unseen board jobs must only follow a successful save."""
import importlib
import sys

import pytest


@pytest.fixture
def ingest(monkeypatch, tmp_path):
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)  # ingestion.log
    sys.modules.pop("ingest_sources", None)
    yield importlib.import_module("ingest_sources")
    sys.modules.pop("ingest_sources", None)


def test_failed_save_closes_nothing(ingest, monkeypatch):
    closed = []
    monkeypatch.setattr(ingest, "save_to_database", lambda *a: None)
    monkeypatch.setattr(ingest, "close_unseen_for", lambda *a: closed.append(a))
    assert ingest.persist(["job"], object(), "greenhouse", "b1", since="t0") is None
    assert closed == []


def test_successful_save_closes_unseen(ingest, monkeypatch):
    closed = []
    monkeypatch.setattr(ingest, "save_to_database", lambda *a: 3)
    monkeypatch.setattr(ingest, "close_unseen_for", lambda *a: closed.append(a[1:]))
    assert ingest.persist(["job"], object(), "greenhouse", "b1", since="t0") == 3
    assert closed == [("greenhouse", "t0")]
