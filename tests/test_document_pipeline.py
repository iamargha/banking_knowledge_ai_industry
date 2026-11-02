from app.document_pipeline import chunk_page, sha256

def test_chunk_page_preserves_content():
    text = ('Policy sentence. ' * 200).strip()
    chunks = chunk_page(text, 300, 40)
    assert len(chunks) > 1
    assert all(chunks)
    assert chunks[0][:20] == text[:20]

def test_sha256_is_stable():
    assert sha256(b'abc') == sha256(b'abc')
    assert sha256(b'abc') != sha256(b'abd')
