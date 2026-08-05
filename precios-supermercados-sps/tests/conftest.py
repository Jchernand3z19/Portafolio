"""Permite ejecutar pytest desde la raíz del monorepositorio."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
