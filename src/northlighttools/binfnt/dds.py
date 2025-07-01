from io import BytesIO
from struct import pack

import numpy as np

from northlighttools.binfnt.constants import DDS_BGRA8_HEADER


class DDS:

    @staticmethod
    def convert_to_bgra8(r16f_data: bytes):
        reader = BytesIO(r16f_data)

        reader.seek(12)
        textureHeight = int.from_bytes(reader.read(4), "little")
        textureWidth = int.from_bytes(reader.read(4), "little")
        reader.seek(84)

        if int.from_bytes(reader.read(4), "little") != 111:
            raise ValueError("Texture is not in R16_FLOAT pixel format!")

        reader.seek(128)

        writer = BytesIO()
        writer.write(DDS_BGRA8_HEADER[:12])
        writer.write(textureHeight.to_bytes(4, "little"))
        writer.write(textureWidth.to_bytes(4, "little"))
        writer.write((textureWidth * 2).to_bytes(4, "little"))
        writer.write(DDS_BGRA8_HEADER[24:])

        for _ in range(textureWidth * textureHeight):
            hGray = np.frombuffer(reader.read(2), dtype=np.float16)[0]
            hGray = np.nan_to_num(hGray, nan=255)
            alpha = int(np.clip(((9 - hGray) * 255) / 18, 0, 255))
            writer.write(
                pack("BBBB", *((255, 255, 255, alpha) if alpha > 0 else (0, 0, 0, 0)))
            )

        return writer.getvalue()
