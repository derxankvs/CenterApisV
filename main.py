# 📦 Imports
import os
import json
import asyncio
import httpx
import re
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telethon import TelegramClient

# 🔧 Carregar variáveis de ambiente
load_dotenv("config.env")

# 🔑 Configurações do Telegram e API
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
API_LAYER_KEY = os.getenv("API_LAYER_KEY")

# 🗂️ Sessões e Grupos
SESSION_V1 = "consultav2.session"
GROUP_V1 = -1001919212067

SESSION_V3 = "telegramv3.session"
GROUP_V3 = -1001919212067

# 🔌 Inicializar clientes Telegram
client_v1 = TelegramClient(SESSION_V1, API_ID, API_HASH)
client_v3 = TelegramClient(SESSION_V3, API_ID, API_HASH)

# 🚀 Inicializar FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 📁 Banco de Dados JSON
DB_PATH = "db/consultas.json"
os.makedirs("db", exist_ok=True)
if not os.path.exists(DB_PATH):
    with open(DB_PATH, "w") as f:
        json.dump([], f)

def salvar_consulta(ip, tipo, dado):
    try:
        with open(DB_PATH, "r") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        dados = []

    dados.append({"ip": ip, "tipo": tipo, "dado": dado})

    with open(DB_PATH, "w") as f:
        json.dump(dados, f, indent=2)

# 🧼 Função para limpar a resposta
def limpar_resposta(texto):
    # Remove emojis (caracteres que não são letras, números, pontuação ou símbolos de URL)
    texto = re.sub(r'[^\w\s.,:;!?@/:\-_]', '', texto)

    # Remove asteriscos e underscores
    texto = texto.replace("*", "").replace("_", "")

    # Remove menções @nome
    texto = re.sub(r'@\w+', '', texto)

    # Remove múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto

# 🌐 Rotas de página (HTML)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/credito", response_class=HTMLResponse)
async def credito(request: Request):
    return templates.TemplateResponse("credito.html", {"request": request})

# 📡 APIs de Consulta
@app.get("/v1/{tipo}/{dado}")
async def consulta_v1(tipo: str, dado: str, request: Request):
    tipos = ["cpf", "nome", "cnpj", "cep", "telefone", "ddd", "ip", "email", "whois"]
    if tipo in tipos:
        salvar_consulta(request.client.host, tipo, dado)
        return await enviar_para_telegram(client_v1, GROUP_V1, tipo, dado)
    return JSONResponse({"erro": "Tipo inválido"}, status_code=400)

@app.get("/v2/{tipo}/{dado}")
async def consulta_v2(tipo: str, dado: str, request: Request):
    tipos = ["cpf", "nome", "cnpj", "cep", "telefone", "ddd", "ip", "email", "rg", "whois", "placa", "foto"]
    if tipo in tipos:
        salvar_consulta(request.client.host, tipo, dado)
        return await enviar_para_telegram(client_v1, GROUP_V1, tipo, dado)
    return JSONResponse({"erro": "Tipo inválido"}, status_code=400)

@app.get("/v3/{tipo}/{dado}")
async def consulta_v3(tipo: str, dado: str, request: Request):
    tipos = [
        "cpf", "telefone", "nome", "placa", "bin", "site", "ip", "cep", "vizinhos", "cnpj", "score",
        "titulo", "email", "vacina", "parentes", "rg", "senha", "foto", "mae", "pai", "chassi", "motor",
        "beneficios", "impostos", "nascimento", "pix", "cns", "correios", "radar", "dominio", "internet",
        "compras", "instagram", "whatsapp", "cnh", "funcionarios", "obito", "logins"
    ]
    if tipo in tipos:
        salvar_consulta(request.client.host, tipo, dado)
        return await enviar_para_telegram(client_v3, GROUP_V3, tipo, dado)
    return JSONResponse({"erro": "Tipo inválido"}, status_code=400)

# 📤 Envio para Telegram com retorno de .txt
async def enviar_para_telegram(client, group_id, tipo, dado):
    try:
        async with client:
            msg = await client.send_message(group_id, f"/{tipo} {dado}")

            from telethon.events import NewMessage

            resposta_final = None

            @client.on(NewMessage(chats=group_id))
            async def handler(event):
                nonlocal resposta_final
                texto = event.text.lower()

                # Ignora mensagens que dizem "aguarde" ou parecidas
                if "aguarde" in texto or "carregando" in texto or "processando" in texto:
                    return

                # Garante que está respondendo à consulta atual
                if event.reply_to_msg_id == msg.id or dado in texto:
                    resposta_final = event.text

            # Espera até 10 segundos por uma resposta real
            for _ in range(20):
                if resposta_final:
                    break
                await asyncio.sleep(0.5)

            client.remove_event_handler(handler, NewMessage)

            if resposta_final:
                texto_limpo = limpar_resposta(resposta_final)
                return {
                    "tipo": tipo,
                    "dado": dado,
                    "resposta": texto_limpo,
                    "criador": "CenterApis - derxan.kvs",
                    "site": "https://centerseven7.netlify.app"
                }
            else:
                return JSONResponse({"erro": "Sem resposta final após aguardar"}, status_code=504)

    except Exception as e:
        return JSONResponse({"erro": f"Erro ao enviar consulta: {str(e)}"}, status_code=500)

# 🌍 API Externa (whois e ddd)
@app.get("/externa/{tipo}/{valor}")
async def externo(tipo: str, valor: str, request: Request):
    salvar_consulta(request.client.host, tipo, valor)
    try:
        if tipo == "whois":
            url = f"https://api.apilayer.com/whois/query?domain={valor}"
            headers = {"apikey": API_LAYER_KEY}
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers)
                data = res.json()

        elif tipo == "ddd":
            url = f"https://brasilapi.com.br/api/ddd/v1/{valor}"
            async with httpx.AsyncClient() as client:
                res = await client.get(url)
                data = res.json()

        else:
            return JSONResponse({"erro": "Tipo externo inválido"}, status_code=400)

        return {
            "criador": "CenterApis - derxan.kvs",
            "site": "https://centerseven7.netlify.app",
            "resultado": data
        }

    except Exception as e:
        return JSONResponse({"erro": f"Erro externo: {str(e)}"}, status_code=500)
