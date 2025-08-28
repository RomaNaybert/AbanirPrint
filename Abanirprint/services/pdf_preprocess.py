import os
import uuid
import tempfile
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2 import Transformation
from tempfile import NamedTemporaryFile
import fitz  # pymupdf
from math import ceil
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def render_pages_to_images(pdf_path: str, selected_pages: list[int]) -> list[str]:
    doc = fitz.open(pdf_path)
    image_paths = []

    for i in selected_pages:
        page = doc[i - 1]
        pix = page.get_pixmap(dpi=150)
        tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.png")
        pix.save(tmp_path)
        image_paths.append(tmp_path)

    return image_paths

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from math import ceil
import tempfile
import os
from PIL import Image

def generate_n_up_pdf(image_paths: list[str], pages_per_sheet: int) -> str:
    c_width, c_height = A4
    pages = ceil(len(image_paths) / pages_per_sheet)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp_file.name, pagesize=A4)

    positions = {
        1: [(0, 0)],
        2: [(0, c_height / 2), (0, 0)],
        4: [
            (0, c_height / 2), (c_width / 2, c_height / 2),
            (0, 0), (c_width / 2, 0)
        ]
    }

    for page in range(pages):
        group = image_paths[page * pages_per_sheet : (page + 1) * pages_per_sheet]

        for i, img_path in enumerate(group):
            x, y = positions[pages_per_sheet][i]

            # Загружаем изображение и масштабируем
            with Image.open(img_path) as img:
                img_width, img_height = img.size
                aspect = img_width / img_height

                # Рассчитываем область для размещения
                target_w = c_width / 2 if pages_per_sheet == 4 else c_width
                target_h = c_height / 2 if pages_per_sheet >= 2 else c_height

                scale = min(target_w / img_width, target_h / img_height)
                new_w = img_width * scale
                new_h = img_height * scale

                offset_x = x + (target_w - new_w) / 2
                offset_y = y + (target_h - new_h) / 2

                c.drawImage(img_path, offset_x, offset_y, width=new_w, height=new_h)

        c.showPage()

    c.save()
    return tmp_file.name

def extract_pages(original_path: str, page_numbers: list[int]) -> str:
    reader = PdfReader(original_path)
    writer = PdfWriter()

    for p in page_numbers:
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p - 1])

    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        writer.write(temp_file)
        return temp_file.name

def duplicate_pdf(filepath: str, copies: int) -> str:
    reader = PdfReader(filepath)
    writer = PdfWriter()

    for _ in range(copies):
        for page in reader.pages:
            writer.add_page(page)

    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        writer.write(temp_file)
        return temp_file.name

def parse_page_range(page_range_str: str, total_pages: int) -> list[int]:
    """
    Превращает диапазон страниц в список.
    "1-3,5,7" => [1, 2, 3, 5, 7]
    """
    pages = set()
    for part in page_range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            if start.isdigit() and end.isdigit():
                pages.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            pages.add(int(part))

    # фильтрация лишних страниц
    return sorted([p for p in pages if 1 <= p <= total_pages]) or list(range(1, total_pages + 1))

def get_page_numbers_from_range(page_range_str: str, total_pages: int) -> list[int]:
    pages = set()
    for part in page_range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            if start.isdigit() and end.isdigit():
                pages.update(range(int(start), int(end)+1))
        elif part.isdigit():
            pages.add(int(part))
    return sorted([p for p in pages if 1 <= p <= total_pages]) or list(range(1, total_pages + 1))

def count_pages_from_range(page_range_str: str, total_pages: int) -> int:
    return len(get_page_numbers_from_range(page_range_str, total_pages))