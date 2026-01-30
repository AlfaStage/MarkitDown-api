from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from pydantic import BaseModel
from markitdown import MarkItDown
import tempfile
import os
import uuid
import base64
import mimetypes
import pytesseract
from PIL import Image
import io

app = FastAPI(
    title="MarkItDown API",
    description="Converte qualquer documento suportado pelo MarkItDown em Markdown",
    version="1.3.0"
)

# 🔐 API KEY via ENV
API_KEY = os.getenv("API_KEY")

# 📦 limite de tamanho (em bytes) – opcional
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default

# Inicializa o MarkItDown uma vez
md = MarkItDown()

class Base64ConvertRequest(BaseModel):
    filename: str
    mimetype: str
    base64_content: str

def get_extension(filename: str, mimetype: str) -> str:
    """Tenta obter a extensão correta do arquivo."""
    ext = os.path.splitext(filename)[1]
    if not ext and mimetype:
        ext = mimetypes.guess_extension(mimetype)
    return ext or ""

def run_ocr(contents: bytes) -> str:
    """Executa o OCR em uma imagem."""
    try:
        image = Image.open(io.BytesIO(contents))
        # Tenta extrair texto em Português e Inglês
        text = pytesseract.image_to_string(image, lang='por+eng')
        return text.strip()
    except Exception as e:
        print(f"Erro no OCR: {e}")
        return ""

def perform_conversion(contents: bytes, filename: str, mimetype: str):
    """Lógica central de conversão usando MarkItDown e OCR como fallback."""
    if len(contents) == 0:
        raise HTTPException(400, "Arquivo vazio")

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo maior que o limite permitido ({MAX_FILE_SIZE} bytes)"
        )

    ext = get_extension(filename, mimetype).lower()
    suffix = ext if ext.startswith(".") else f".{ext}" if ext else ""
    
    is_image = mimetype.startswith("image/") or ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
    markdown = ""

    # Tenta conversão via MarkItDown primeiro
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(contents)
        tmp_path = tmp_file.name

    try:
        result = md.convert(tmp_path)
        markdown = result.text_content.strip() if result else ""
    except Exception as e:
        # Se falhar e for imagem, ignoramos o erro para tentar OCR abaixo
        if not is_image:
            raise HTTPException(
                status_code=500,
                detail={"message": "Erro ao converter arquivo", "error": str(e)}
            )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Fallback para OCR se for imagem e o MarkItDown não retornou texto satisfatório
    if is_image and (not markdown or len(markdown) < 10):
        ocr_text = run_ocr(contents)
        if ocr_text:
            markdown = ocr_text

    if not markdown:
        raise HTTPException(
            status_code=422,
            detail="Conversão concluída, mas nenhum texto foi extraído (Markdown vazio)"
        )

    return {
        "filename": filename,
        "content_type": mimetype,
        "size_bytes": len(contents),
        "markdown": markdown,
        "method": "ocr" if is_image and not (result and result.text_content.strip()) else "markitdown"
    }

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    x_api_key: str = Header(None)
):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    contents = await file.read()
    return perform_conversion(contents, file.filename, file.content_type)

@app.post("/convert-base64")
async def convert_base64(
    request: Base64ConvertRequest,
    x_api_key: str = Header(None)
):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        b64_str = request.base64_content
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
        contents = base64.b64decode(b64_str)
    except Exception:
        raise HTTPException(400, "Conteúdo Base64 inválido")

    return perform_conversion(contents, request.filename, request.mimetype)
