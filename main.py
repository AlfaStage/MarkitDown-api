from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import subprocess
import tempfile
import os

app = FastAPI(
    title="MarkItDown API",
    description="Converte documentos em Markdown",
    version="1.0.0"
)

API_KEY = os.getenv("API_KEY")

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    x_api_key: str = Header(None)
):
    # 🔐 valida API key
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

    # 📂 diretório temporário
    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, file.filename)

        with open(input_path, "wb") as f:
            f.write(await file.read())

        # ▶️ executa o markitdown
        result = subprocess.run(
            ["markitdown", input_path],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=result.stderr
            )

        # 📄 markdown vem direto no stdout
        return {
            "filename": file.filename,
            "markdown": result.stdout
        }
