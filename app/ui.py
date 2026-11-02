import os, requests, streamlit as st
st.set_page_config(page_title='Banking Knowledge AI', page_icon='🏦', layout='wide')
st.title('Banking Knowledge AI')
st.caption('Reference implementation • Gemini • LangGraph • Milvus • local demo identity only')
api = os.getenv('API_URL', 'http://localhost:8000')
key = os.getenv('APP_API_KEY', '')
with st.sidebar:
    st.warning('Use synthetic/public PDFs only. This local UI is not a bank-grade identity provider.')
    department = st.selectbox('Department', ['PUBLIC','OPERATIONS','RISK','COMPLIANCE','HR'])
    document_id = st.text_input('Document ID', 'DEMO-POLICY-001')
    version = st.text_input('Version', '1.0')
tab1, tab2 = st.tabs(['Ingest document', 'Ask knowledge base'])
with tab1:
    pdf = st.file_uploader('PDF document', type=['pdf'])
    if st.button('Ingest', disabled=pdf is None):
        with st.spinner('Extracting, chunking, embedding and indexing...'):
            response = requests.post(f'{api}/v1/documents', headers={'X-API-Key':key}, data={'department':department,'document_id':document_id,'version':version}, files={'file':(pdf.name,pdf.getvalue(),'application/pdf')}, timeout=300)
        if response.ok: st.success(response.json())
        else: st.error(response.text)
with tab2:
    question = st.text_area('Question')
    if st.button('Ask', disabled=not question.strip()):
        with st.spinner('Retrieving authorised evidence and generating a grounded answer...'):
            response = requests.post(f'{api}/v1/chat', headers={'X-API-Key':key}, json={'question':question}, timeout=180)
        if response.ok:
            payload=response.json(); st.markdown(payload['answer']); st.caption(f"Request: {payload['request_id']} • Abstained: {payload['abstained']}")
            st.subheader('Evidence')
            for source in payload['sources']:
                st.write(f"{source['filename']} • page {source['page']} • document {source['document_id']} • version {source['version']} • score {source['score']}")
        else: st.error(response.text)
