from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import subprocess
import tempfile
import os
import shutil
import uuid

app = FastAPI(
    title="MarkItDown API",
    description="Converte qualquer documento suportado pelo MarkItDown em Markdown",
    version="1.1.0"
)

# 🔐 API KEY via ENV
API_KEY = os.getenv("API_KEY")

# 📦 limite de tamanho (em bytes) – opcional
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    x_api_key: str = Header(None)
):
    # ─────────────────────
    # Segurança
    # ─────────────────────
    if API_KEY is None:
        raise HTTPException(
            status_code=500,
            detail="API_KEY não configurada no ambiente"
        )

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    # ─────────────────────
    # Leitura do arquivo
    # ─────────────────────
    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(400, "Arquivo vazio")

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo maior que o limite permitido ({MAX_FILE_SIZE} bytes)"
        )

    # ─────────────────────
    # Diretório temporário
    # ─────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        safe_name = file.filename or f"file-{uuid.uuid4()}"
        input_path = os.path.join(tmp, safe_name)

        with open(input_path, "wb") as f:
            f.write(contents)

        # ─────────────────────
        # Execução do MarkItDown
        # ─────────────────────
        result = subprocess.run(
            ["markitdown", input_path],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Erro ao converter arquivo",
                    "stderr": result.stderr
                }
            )

        markdown = result.stdout.strip()

        if not markdown:
            raise HTTPException(
                status_code=422,
                detail="Conversão concluída, mas o Markdown está vazio"
            )

        # ─────────────────────
        # Resposta
        # ─────────────────────
        return {
            "filename": safe_name,
            "content_type": file.content_type,
            "size_bytes": len(contents),
            "markdown": markdown
        }
