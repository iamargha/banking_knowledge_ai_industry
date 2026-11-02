import logging, uuid
from datetime import date
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, Depends
from .config import settings
from .schemas import ChatRequest, ChatResponse, IngestResponse, Source
from .security import require_demo_identity
from .document_pipeline import validate_pdf, extract_pages, sha256, build_chunks
from .services import AIService, VectorStore
from .graph import build_graph

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger('banking-rag')
app = FastAPI(title='Banking Knowledge AI Platform', version='1.0.0', description='Production-oriented reference architecture; deployment hardening required.')
ai = None
store = None
rag = None

@app.on_event('startup')
def startup():
    global ai, store, rag
    ai = AIService()
    store = VectorStore()
    rag = build_graph(ai, store)

@app.get('/health/live')
def live():
    return {'status': 'alive'}

@app.get('/health/ready')
def ready():
    if ai is None or store is None or rag is None:
        raise HTTPException(status_code=503, detail='Service dependencies are not ready')
    return {'status': 'ready', 'embedding_model': settings.gemini_embedding_model, 'chat_model': settings.gemini_chat_model, 'collection': settings.qdrant_collection}

@app.post('/v1/documents', response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    department: str = Form(...),
    document_type: str = Form('POLICY'),
    document_id: str = Form(...),
    version: str = Form('1'),
    effective_date: date | None = Form(None),
    classification: str = Form('INTERNAL'),
    identity: dict = Depends(require_demo_identity),
):
    # Local demo identity only. Production must validate uploader role and approved metadata.
    if department.upper() not in identity['departments']:
        raise HTTPException(status_code=403, detail='Uploader is not authorised for this department')
    if file.content_type not in ('application/pdf', 'application/octet-stream'):
        raise HTTPException(status_code=415, detail='Only PDF content is accepted')
    data = await file.read((settings.max_upload_mb * 1024 * 1024) + 1)
    try:
        validate_pdf(data, settings.max_upload_mb * 1024 * 1024)
        pages, warnings = extract_pages(data)
        digest = sha256(data)
        metadata = {
            'department': department.upper(), 'document_type': document_type.upper(),
            'document_id': document_id, 'version': version,
            'effective_date': effective_date.isoformat() if effective_date else '',
            'classification': classification.upper(),
        }
        rows = build_chunks(pages, metadata, file.filename or 'unnamed.pdf', digest, settings.chunk_size, settings.chunk_overlap)
        if not rows:
            raise ValueError('No extractable text found. Install and configure the OCR adapter for scanned PDFs.')
        vectors = [ai.embed(row['text'], 'RETRIEVAL_DOCUMENT') for row in rows]
        store.insert(rows, vectors)
        log.info('document_ingested document_id=%s version=%s pages=%d chunks=%d sha256=%s', document_id, version, len(pages), len(rows), digest)
        return IngestResponse(status='indexed', document_id=document_id, content_sha256=digest, pages_processed=len(pages), chunks_indexed=len(rows), warnings=warnings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        log.exception('document_ingestion_failed request_id=%s', uuid.uuid4())
        raise HTTPException(status_code=502, detail='Document ingestion failed; check service logs using the request correlation id') from exc

@app.post('/v1/chat', response_model=ChatResponse)
def chat(request: ChatRequest, identity: dict = Depends(require_demo_identity)):
    request_id = str(uuid.uuid4())
    try:
        result = rag.invoke({'question': request.question, 'identity': identity, 'top_k': request.top_k})
        sources = [Source(**source) for source in result.get('sources', [])]
        return ChatResponse(answer=result.get('answer', ''), sources=sources, request_id=request_id, abstained=result.get('abstained', False))
    except Exception as exc:
        log.exception('chat_failed request_id=%s', request_id)
        raise HTTPException(status_code=502, detail=f'Unable to complete request. Reference: {request_id}') from exc
