import streamlit as st
import requests
import json
import os
import docx
import fitz
from io import BytesIO
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import GoogleGenerativeAIEmbeddings

# --- CONFIGURAÇÃO DA INTERFACE (Streamlit) ---
st.set_page_config(page_title="Chatbot de Documento Fixo")
st.title("Chatbot – Gerência de Informação Legislativa")
st.write("Selecione um assunto para iniciar a conversa.")

# --- LISTA DE DOCUMENTOS PRÉ-DEFINIDOS ---
DOCUMENTOS_PRE_CARREGADOS = {
    "Constituição Estadual": "constituicao.pdf",
    # Adicione outros documentos aqui
}

# --- PROMPTS PERSONALIZADOS POR DOCUMENTO ---
PROMPTS_POR_DOCUMENTO = {
    "Constituição Estadual": """
    Personalização da IA:
    Você é um assistente especializado na Constituição do Estado de Minas Gerais.
    Sua única fonte de informação são os trechos do documento fornecidos.

    ====================================================================

    Regras de Resposta:
    - Responda de forma objetiva, formal e clara.
    - Se a informação não estiver nos trechos do documento, responda: "A informação não foi encontrada nos trechos do documento."
    - Para cada resposta, forneça uma explicação detalhada. Sempre que possível, cite os artigos, parágrafos e incisos relevantes da Constituição.
    - Sempre cite a fonte da sua resposta. A fonte deve ser a página onde a informação foi encontrada, no seguinte formato: "Você pode verificar a informação na página [cite a página] da Constituição Estadual."

    ---
    Trechos do Documento:
    {conteudo_do_documento}
    ---
    Pergunta: {pergunta_usuario}
    """,
}

def get_api_key():
    api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("Erro: A chave de API não foi configurada.")
        return None
    return api_key

def create_vector_store(file_path):
    """
    Cria e retorna um vector store (ChromaDB) a partir do documento.
    """
    if not os.path.exists(file_path):
        st.error(f"Erro: O arquivo '{file_path}' não foi encontrado.")
        return None

    try:
        # Carrega o documento
        loader = PyMuPDFLoader(file_path)
        pages = loader.load()

        # Divide o documento em chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(pages)

        # Cria os embeddings e o vector store
        embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=get_api_key())
        vector_store = Chroma.from_documents(chunks, embeddings_model)
        return vector_store
    except Exception as e:
        st.error(f"Ocorreu um erro ao criar o vector store: {e}")
        return None

def answer_from_document_rag(pergunta_usuario, vector_store, prompt_template, api_key):
    """
    Gera uma resposta usando a abordagem RAG.
    """
    if not api_key or not vector_store:
        return "Erro: Chave de API ausente ou vector store não criado."

    try:
        # Busca os trechos mais relevantes do documento
        relevant_docs = vector_store.similarity_search(pergunta_usuario, k=3)
        relevant_text = "\n\n".join([doc.page_content for doc in relevant_docs])

        # Cria o prompt com os trechos relevantes
        prompt_completo = prompt_template.format(
            conteudo_do_documento=relevant_text,
            pergunta_usuario=pergunta_usuario
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt_completo}]}]}

        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        resposta = result.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "Não foi possível gerar a resposta.")
        return resposta
    except requests.exceptions.HTTPError as http_err:
        return f"Erro na comunicação com a API: {http_err}"
    except Exception as e:
        return f"Ocorreu um erro: {e}"

# --- SELEÇÃO DE DOCUMENTO E INÍCIO DO CHAT ---

file_names = list(DOCUMENTOS_PRE_CARREGADOS.keys())
if not file_names:
    st.warning("Nenhum documento pré-carregado. Por favor, adicione arquivos à lista `DOCUMENTOS_PRE_CARREGADOS`.")
else:
    selected_file_name_display = st.selectbox("Escolha o assunto sobre o qual você quer conversar:", file_names)
    selected_file_path = DOCUMENTOS_PRE_CARREGADOS[selected_file_name_display]
    
    if selected_file_name_display in PROMPTS_POR_DOCUMENTO:
        prompt_base = PROMPTS_POR_DOCUMENTO[selected_file_name_display]
    else:
        st.error("Erro: Não foi encontrado um prompt personalizado para este documento.")
        prompt_base = "Responda a pergunta do usuário com base nos seguintes trechos do documento: {conteudo_do_documento}. Pergunta: {pergunta_usuario}"
    
    if "vector_store" not in st.session_state or st.session_state.vector_store_name != selected_file_name_display:
        st.session_state.vector_store_name = selected_file_name_display
        st.session_state.vector_store = create_vector_store(selected_file_path)

    if st.session_state.vector_store:
        st.success(f"Documento '{selected_file_name_display}' carregado com sucesso!")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if pergunta_usuario := st.chat_input("Faça sua pergunta:"):
            st.session_state.messages.append({"role": "user", "content": pergunta_usuario})
            
            with st.chat_message("user"):
                st.markdown(pergunta_usuario)

            with st.chat_message("assistant"):
                with st.spinner("Buscando a resposta..."):
                    api_key = get_api_key()
                    if api_key and st.session_state.vector_store:
                        resposta = answer_from_document_rag(
                            pergunta_usuario,
                            st.session_state.vector_store,
                            prompt_base,
                            api_key
                        )
                        st.markdown(resposta)
            
                        st.session_state.messages.append({"role": "assistant", "content": resposta})

    if st.button("Limpar Chat"):
        st.session_state.messages = []
        st.rerun()
