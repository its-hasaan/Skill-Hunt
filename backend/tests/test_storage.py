import re

from app import storage


class FakeBucket:
    def __init__(self):
        self.uploads = []

    def upload(self, path, data, options):
        self.uploads.append((path, data, options))

    def get_public_url(self, path):
        raise AssertionError("resumes live in a private bucket; never build public URLs")


class FakeClient:
    def __init__(self):
        self.bucket = FakeBucket()
        self.storage = self

    def from_(self, name):
        assert name == "resumes"
        return self.bucket


async def test_upload_returns_only_the_storage_path(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(storage, "_get_client", lambda: client)
    path = await storage.upload_resume_file(b"%PDF-1.7", "cv.pdf")
    assert re.fullmatch(r"\d{4}/\d{2}/[0-9a-f-]{36}_cv\.pdf", path)
    (_, data, options), = client.bucket.uploads
    assert data == b"%PDF-1.7"
    assert options["content-type"] == "application/pdf"
