"""二维码生成器 — 实现 QRCodePort。"""

import qrcode
from rich.console import Console

console = Console()


class QRGeneratorAdapter:
    """实现 QRCodePort，生成终端 ASCII 二维码和 PNG 文件。"""

    def generate_ascii(self, url: str) -> None:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        for y in range(0, len(matrix), 2):
            line = []
            for x in range(len(matrix[0])):
                top = matrix[y][x]
                bot = matrix[y + 1][x] if y + 1 < len(matrix) else False
                if top and bot:
                    line.append("█")
                elif top:
                    line.append("▀")
                elif bot:
                    line.append("▄")
                else:
                    line.append(" ")
            console.print("".join(line), end="")
            console.print()

    def save_png(self, url: str, filepath: str) -> None:
        img = qrcode.make(url)
        img.save(filepath)