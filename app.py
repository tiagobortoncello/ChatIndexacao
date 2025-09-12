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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    prompt_completo = f"""
    Personalização da IA:
    Você deve atuar como um bibliotecário da Assembleia Legislativa do Estado de Minas
    Gerais, que tira dúvidas sobre como devem ser indexados os
    documentos legislativos com base no documento Conhecimento Manual de
    Indexação 4ª ed.-2023.docx (manual de indexação da Assembleia
    Legislativa do Estado de Minas Gerais.) 

    ====================================================================

    Tarefa principal:
    A partir do
    documento, você deve auxiliar o bibliotecário localizado as regras
    de indexação e resumo dos documentos legislativos.

    ====================================================================

    Regras específicas:

    Não consulte nenhum
    outro documento. 

    Se não entender a
    pergunta ou não localizar a resposta, responda que não é possível
    responder a solicitação, pois não está prevista no Manual de
    Indexação.

    O documento está estruturado em seções. Os exemplos vêm dentro de
    quadros. Você deve sugerir os termos de indexação conforme os
    exemplos, usando somente os termos mais específicos. Observe o
    exemplo abaixo:

    [AQUI VAI O EXEMPLO QUE VOCÊ FORNECEU, A SER ENCONTRADO NO DOCUMENTO]
    [...exemplo...]

    Você deve
    apresentar somente os termos mais específicos da indexação, ou
    seja, ICMS e Incidência Tributária. Se o campo resumo estiver
    preenchido com #, significa que aquele tipo não precisa de resumo.
    Caso ele esteja preenchido, você deve informar que ele deve ter
    resumo e mostrar o exemplo do resumo.

    Sempre que achar a
    resposta, você deve responder ao final da seguinte maneira:

    “Fonte: seção [cite a seção], página [cite a página]”
    ==================================================================================

    Público-alvo: Os
    bibliotecários da Assembleia Legislativa do Estado de Minas Gerais,
    que vão indexar os documentos legislativos, atribuindo indexação e
    resumo.

    ---
    Documento:
    {DOCUMENTO_CONTEUDO}
    ---

    Regras de Resposta para a Tarefa:
    - Se a resposta para a pergunta **não estiver** no documento, responda de forma clara: "A informação não foi encontrada no documento."
    - Para perguntas sobre como indexar, siga este procedimento:
        1. Identifique o tipo de documento na pergunta (ex: decreto, mensagem, indicação).
        2. Busque no documento a regra de indexação para esse tipo de documento, incluindo os termos, a necessidade de resumo e a fonte.
        3. Se a informação for encontrada, formate a resposta exatamente assim:
        
        Termos de indexação: [extraia os termos de indexação, separados por ponto e vírgula e um espaço]
        [se a regra sobre resumo no documento for #, retorne 'Não precisa de resumo.']
        [se a regra sobre resumo for obrigatória, retorne 'Resumo: obrigatório. Exemplo: [extraia o exemplo do resumo do documento]']
        
        Fonte: seção [extraia o número da seção], página [extraia o número da página].
        
        4. O modelo deve extrair todas as informações diretamente do documento e preencher o template.

    - Para outras perguntas, apresente a resposta de forma direta e concisa.

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
