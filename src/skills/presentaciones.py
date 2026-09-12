import os
import json
def slide_builder(params):
    # Suponiendo que 'params' contiene la información necesaria para construir la presentación
    slides = []
    for slide in params.get('slides', []):
        slide_content = {
            'title': slide.get('title', 'Untitled'),
            'content': slide.get('content', ''),
            'image_path': os.path.join(os.getcwd(), slide.get('image', 'default.jpg'))
        }
        slides.append(slide_content)
    return slides
def run(params):
    return slide_builder(params)