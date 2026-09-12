from PIL import Image, ImageFilter, ImageEnhance
from pathlib import Path

class ImageEditor:
    def process(self, image_path: str, filter_type: str = None,
                brightness: float = 1.0, contrast: float = 1.0,
                sharpness: float = 1.0) -> str:
        if not Path(image_path).exists():
            return f"Imagen no encontrada: {image_path}"
        img = Image.open(image_path)

        if filter_type:
            filters = {
                "blur": ImageFilter.BLUR,
                "contour": ImageFilter.CONTOUR,
                "detail": ImageFilter.DETAIL,
                "edge": ImageFilter.EDGE_ENHANCE,
                "emboss": ImageFilter.EMBOSS,
                "sharpen": ImageFilter.SHARPEN,
                "smooth": ImageFilter.SMOOTH,
            }
            if filter_type in filters:
                img = img.filter(filters[filter_type])

        if brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(brightness)
        if contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)
        if sharpness != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(sharpness)

        output_path = Path(image_path).parent / f"edited_{Path(image_path).stem}.png"
        img.save(output_path)
        return f"Imagen guardada: {output_path}"