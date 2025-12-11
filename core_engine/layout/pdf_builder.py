from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from core_engine.core.models import BookDocument, BlockType


class PDFBuilder:
    """
    Простой лэйаутер:
    - один поток текста сверху вниз
    - без картинок и сложной верстки (это позже)
    Интерфейс:
        builder = PDFBuilder()
        builder.build_pdf(doc, "output.pdf")
    """

    def __init__(self, page_size=A4, margin: float = 50.0):
        self.page_size = page_size
        self.margin = margin

    def _draw_block(self, c: canvas.Canvas, text: str, y: float, is_heading: bool) -> float:
        """
        Рисуем один текстовый блок, возвращаем новый y-курсор.
        """
        width, height = self.page_size
        margin = self.margin

        font_size = 12 if is_heading else 10
        line_height = font_size * 1.2
        c.setFont("Times-Roman", font_size)

        for line in text.split("\n"):
            # если не влезаем по высоте — новая страница
            if y < margin:
                c.showPage()
                y = height - margin
                c.setFont("Times-Roman", font_size)

            c.drawString(margin, y, line)
            y -= line_height

        return y

    def build_pdf(self, doc: BookDocument, output_path: str) -> None:
        """
        Собирает простой PDF по документу.
        """
        c = canvas.Canvas(output_path, pagesize=self.page_size)
        width, height = self.page_size
        margin = self.margin

        for page in doc.pages:
            y = height - margin

            for block in page.blocks:
                text = (
                    block.translated_text
                    or block.normalized_text
                    or block.raw_text
                    or ""
                ).strip()

                if not text:
                    continue

                is_heading = block.type == BlockType.HEADING
                y = self._draw_block(c, text, y, is_heading)

            # после страницы явно переходим на следующую
            c.showPage()

        c.save()

