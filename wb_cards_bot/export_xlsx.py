"""Экспорт карточек в Excel для массовой загрузки на маркетплейс."""

from openpyxl import Workbook


def card_to_xlsx(cards: list, filename: str = "cards.xlsx") -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Карточки"
    ws.append(["Товар", "Категория", "Название (SEO)", "Ключевые слова", "Описание"])
    for c in cards:
        ws.append([c["product"], c["category"], c["title"],
                   c["keywords"], c["description"]])
    for col, width in zip("ABCDE", [24, 16, 45, 50, 70]):
        ws.column_dimensions[col].width = width
    wb.save(filename)
    return filename
