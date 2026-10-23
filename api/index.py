"""
Punto de entrada de Vercel. Es el único archivo .py dentro de api/: Vercel
convierte cada .py de esta carpeta en una función, así que el código vive en
backend/ y aquí solo se importa.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.main import app  # noqa: E402,F401
