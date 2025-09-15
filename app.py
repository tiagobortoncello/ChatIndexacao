import streamlit as st
import requests
import json
import os
import docx
import fitz # PyMuPDF
from io import BytesIO

# --- CONFIGURAÇÃO DA INTERFACE (Streamlit) ---
st.set_page_config(page_title="Chatbot da GIL")
st.title("Chatbot – Gerência de Informação Legislativa")
st.write("Selecione um assunto para iniciar a conversa.")

# --- LISTA DE DOCUMENTOS PRÉ-DEFINIDOS ---
DOCUMENTOS_PRE_CARREGADOS = {
    "Manual de Indexação": "manual_indexacao.pdf",
    "Regimento Interno da ALMG": "regimento.pdf",
    "Constituição Estadual": "constituicao.pdf",
    # Adicione mais documentos aqui, seguindo o formato "Nome Exibido": "nome_do_arquivo.extensão"
}

# --- PROMPTS PERSONALIZADOS POR DOCUMENTO ---
PROMPTS_POR_DOCUMENTO = {
    "Manual de Indexação": """
    Personalização da IA:
    Você deve atuar como um bibliotecário da Assembleia Legislativa do Estado de Minas
    Gerais, que tira dúvidas sobre como devem ser indexados os
    documentos legislativos com base no documento Conhecimento Manual de
    Indexação 4ª ed.-2023.docx.

    ====================================================================

    Tarefa principal:
    A partir do documento, você deve auxiliar o bibliotecário localizado as regras
    de indexação e resumo dos documentos legislativos.

    ====================================================================

    Regras específicas:
    
    Não consulte nenhum
    outro documento. 
    
    Se não entender a
    pergunta ou não localizar a resposta, responda que não é possível
    responder a solicitação, pois não está prevista no Manual de
    Indexação.
    
    ---
    **REGRA OBRIGATÓRIA E FORMATO DE RESPOSTA:**
    
    A sua resposta deve seguir este formato exato, buscando as informações no documento.
    
    **Termos de Indexação:**
    [Liste cada termo em uma nova linha, conforme os exemplos do manual.]
    
    **Resumo:**
    [Verifique o campo 'Resumo:' na tabela do manual para determinar a regra.]
    
    **Regra para o campo Resumo:**
    - Se a coluna à direita do campo 'Resumo:' na tabela contiver um exemplo de texto, informe: "É necessário resumo. Exemplo: [exemplo do manual]."
    - Se a coluna à direita do campo 'Resumo:' na tabela contiver o símbolo '#', informe: "Não é necessário resumo para este tipo de documento."
    
    ---
    
    Sempre que achar a
    resposta, você deve responder ao final da seguinte maneira:
    
    "Você pode verificar a informação na página [cite a página] do Manual de Indexação."
    ==================================================================================

    Público-alvo: Os
    bibliotecários da Assembleia Legislativa do Estado de Minas Gerais,
    que vão indexar os documentos legislativos, atribuindo indexação e
    resumo.

    ---
    Histórico da Conversa:
    {historico_da_conversa}
    ---
    Documento:
    {conteudo_do_documento}
    ---
    Pergunta: {pergunta_usuario}
    """,

    "Regimento Interno da ALMG": """
    Personalização da IA:
    Você é um assistente especializado no Regimento Interno da Assembleia Legislativa de Minas Gerais.
    Sua única fonte de informação é o documento "Regimento Interno da ALMG.pdf".

    ====================================================================

    Regras de Resposta:
    - Responda de forma objetiva, formal e clara.
    - Se a informação não estiver no documento, responda: "A informação não foi encontrada no documento."
    - Para cada resposta, forneça uma explicação detalhada, destrinchando o processo e as regras relacionadas. Sempre que possível, cite os artigos, parágrafos e incisos relevantes do Regimento.
    - Sempre cite a fonte da sua resposta. A fonte deve ser a página onde a informação foi encontrada no documento, no seguinte formato: "Você pode verificar a informação na página [cite a página] do Regimento Interno da ALMG."

    ---
    Histórico da Conversa:
    {historico_da_conversa}
    ---
    Documento:
    {conteudo_do_documento}
    ---
    Pergunta: {pergunta_usuario}
    """,

    "Constituição Estadual": """
    Personalização da IA:
    Você é um assistente especializado na Constituição do Estado de Minas Gerais.
    Sua única fonte de informação é o documento "Constituição Estadual.pdf".

    ====================================================================

    Regras de Resposta:
    - Responda de forma objetiva, formal e clara.
    - Se a informação não estiver no documento, responda: "A informação não foi encontrada no documento."
    - Para cada resposta, forneça uma explicação detalhada, destrinchando o processo e as regras relacionadas. Sempre que possível, cite os artigos, parágrafos e incisos relevantes da Constituição.
    - Sempre cite a fonte da sua resposta. A fonte deve ser a página onde a informação foi encontrada no documento, no seguinte formato: "Você pode verificar a informação na página [cite a página] da Constituição Estadual."

    ---
    Histórico da Conversa:
    {historico_da_conversa}
    ---
    Documento:
    {conteudo_do_documento}
    ---
    Pergunta: {pergunta_usuario}
    """,
    
    # Adicione mais prompts personalizados aqui, mapeando ao nome de cada documento.
}

# --- FUNÇÕES AUXILIARES ---

def carregar_documento_do_disco(caminho_arquivo):
    """
    Carrega o conteúdo de um arquivo do disco local (.txt, .docx, .pdf) em uma string.
    """
    if not os.path.exists(caminho_arquivo):
        st.error(f"Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return None
    
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
    except Exception as e:
        st.error(f"Ocorreu um erro ao ler o arquivo: {e}")
        return None

def get_api_key():
    """
    Tenta obter a chave de API das variáveis de ambiente ou secrets do Streamlit.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("Erro: A chave de API não foi configurada. Por favor, adicione 'GOOGLE_API_KEY' nos segredos do Streamlit ou nas variáveis de ambiente.")
        return None
    return api_key

def answer_from_document(prompt_completo, api_key):
    """
    Gera uma resposta para o prompt usando a API da Gemini.
    """
    if not api_key:
        return "Erro: Chave de API ausente."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

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

# --- SELEÇÃO DE DOCUMENTO E INÍCIO DO CHAT ---

file_names = list(DOCUMENTOS_PRE_CARREGADOS.keys())
if not file_names:
    st.warning("Nenhum documento pré-carregado. Por favor, adicione arquivos à lista `DOCUMENTOS_PRE_CARREGADOS` no código.")
else:
    selected_file_name_display = st.selectbox("Escolha o assunto sobre o qual você quer conversar:", file_names)
    selected_file_path = DOCUMENTOS_PRE_CARREGADOS[selected_file_name_display]
    
    if selected_file_name_display in PROMPTS_POR_DOCUMENTO:
        prompt_base = PROMPTS_POR_DOCUMENTO[selected_file_name_display]
    else:
        st.error("Erro: Não foi encontrado um prompt personalizado para este documento. Usando prompt padrão.")
        prompt_base = "Responda a pergunta do usuário com base no seguinte documento: {conteudo_do_documento}. Pergunta: {pergunta_usuario}"
    
    DOCUMENTO_CONTEUDO = carregar_documento_do_disco(selected_file_path)

    if DOCUMENTO_CONTEUDO:
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
                    if api_key and DOCUMENTO_CONTEUDO:
                        prompt_completo = prompt_base.format(
                            historico_da_conversa=st.session_state.messages,
                            conteudo_do_documento=DOCUMENTO_CONTEUDO,
                            pergunta_usuario=pergunta_usuario
                        )
                        
                        resposta = answer_from_document(prompt_completo, api_key)
                        st.markdown(resposta)
            
                        st.session_state.messages.append({"role": "assistant", "content": resposta})

    if st.button("Limpar Chat"):
        st.session_state.messages = []
        st.rerun()
