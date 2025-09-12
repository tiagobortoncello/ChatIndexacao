import streamlit as st
import requests
import json
import os
import docx
import fitz  # PyMuPDF

# --- CONFIGURAÇÃO DO ARQUIVO ---
# 1. SUBSTITUA PELO NOME DO SEU ARQUIVO DE CONSULTA
# Certifique-se de que ele esteja na mesma pasta do seu script 'app.py'
NOME_DO_ARQUIVO = "manual_indexacao.pdf" 
# -----------------------------

def carregar_documento(caminho_arquivo):
    """
    Carrega o conteúdo de um arquivo (.txt, .docx, .pdf) em uma string.
    """
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    
    try:
        if extensao == ".txt":
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                return f.read()
        elif extensao == ".docx":
            doc = docx.Document(caminho_arquivo)
            texto = [paragrafo.text for paragrafo in doc.paragraphs]
            return "\n".join(texto)
        elif extensao == ".pdf":
            texto = ""
            with fitz.open(caminho_arquivo) as pdf_doc:
                for page in pdf_doc:
                    texto += page.get_text()
            return texto
        else:
            st.error(f"Erro: Formato de arquivo '{extensao}' não suportado.")
            return None
    except FileNotFoundError:
        st.error(f"Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return None
    except Exception as e:
        st.error(f"Ocorreu um erro ao ler o arquivo: {e}")
        return None

# Carrega o documento fixo uma única vez no início
DOCUMENTO_CONTEUDO = carregar_documento(NOME_DO_ARQUIVO)

# Função para obter a chave de API de forma segura
def get_api_key():
    """
    Tenta obter a chave de API das variáveis de ambiente ou secrets do Streamlit.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("Erro: A chave de API não foi configurada. Por favor, adicione 'GOOGLE_API_KEY' nos segredos do Streamlit ou nas variáveis de ambiente.")
        return None
    return api_key

def answer_from_document(pergunta, api_key):
    """
    Gera uma resposta para a pergunta usando apenas o conteúdo do documento lido.
    """
    if not api_key:
        return "Erro: Chave de API ausente."
    if not DOCUMENTO_CONTEUDO:
        return "Erro: Conteúdo do documento não pôde ser carregado."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"

    prompt_completo = f"""
    Você é um assistente de IA. Sua única fonte de conhecimento é o documento fornecido.
    Responda à pergunta do usuário **APENAS** usando as informações contidas no documento abaixo.
    Se a resposta para a pergunta não estiver explicitamente no documento, diga que a informação não foi encontrada.
    Não use seu conhecimento prévio para responder.

    ---
    Documento:
    {DOCUMENTO_CONTEUDO}
    ---
    
    Pergunta: {pergunta}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt_completo}]}]
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        resposta = result.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "Não foi possível gerar a resposta.")
        return resposta
    except requests.exceptions.HTTPError as http_err:
        return f"Erro na comunicação com a API: {http_err}"
    except Exception as e:
        return f"Ocorreu um erro: {e}"

# --- Configuração da Interface (Streamlit) ---
st.set_page_config(page_title="Chatbot de Documento Fixo")
st.title("Chatbot Baseado em Documento Fixo")
st.write("Faça perguntas sobre o documento que está no código-fonte.")

# Área para o usuário fazer a pergunta
pergunta_usuario = st.text_input(
    "Faça sua pergunta:", 
    placeholder="Ex: 'Quais os tipos de plano de assinatura?'"
)

# Botão para enviar a pergunta e gerar a resposta
if st.button("Obter Resposta"):
    if not pergunta_usuario:
        st.warning("Por favor, digite sua pergunta.")
    else:
        api_key = get_api_key()
        if api_key:
            with st.spinner("Buscando a resposta..."):
                resposta = answer_from_document(pergunta_usuario, api_key)
            
            st.subheader("Resposta")

            st.markdown(f"<p style='text-align: justify;'>{resposta}</p>", unsafe_allow_html=True)
