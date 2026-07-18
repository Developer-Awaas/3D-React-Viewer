"""Deploy-correctness tests: the slim (vector-only, no-torch) production
image must boot, and the deploy dependency list must actually cover every
import the vector path makes."""
import os
import subprocess
import sys

SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_BOOT_SNIPPET = r"""
import sys, importlib.abc

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in ('torch', 'torchvision', 'skimage'):
            raise ImportError('blocked: ' + name)

sys.meta_path.insert(0, Block())
import main
assert main.perception is None, 'perception must be disabled without torch'
from fastapi.testclient import TestClient
with TestClient(main.app) as c:
    r = c.get('/health').json()
    assert r['ok'] is True and r['raster_beta'] is False
print('VECTOR_ONLY_BOOT_OK')
"""


def test_boots_without_torch_like_the_docker_image():
    """Simulates the slim Docker image (requirements-deploy.txt has no
    torch): main must import, boot, and report raster_beta=false."""
    r = subprocess.run([sys.executable, "-c", _BOOT_SNIPPET],
                       cwd=SERVER, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert "VECTOR_ONLY_BOOT_OK" in r.stdout


def test_deploy_requirements_cover_vector_path_imports():
    """Every third-party module the vector path can import at runtime must
    appear in requirements-deploy.txt (catches 'works on my machine')."""
    reqs = open(os.path.join(SERVER, "requirements-deploy.txt")).read().lower()
    needed = {          # import name -> requirement line to look for
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "multipart": "python-multipart",
        "dotenv": "python-dotenv",
        "PIL": "pillow",
        "numpy": "numpy",
        "shapely": "shapely",
        "cv2": "opencv-python-headless",
        "trimesh": "trimesh",
        "mapbox_earcut": "mapbox-earcut",
        "fitz": "pymupdf",
    }
    missing = [f"{imp} (needs {req})" for imp, req in needed.items()
               if req not in reqs]
    assert missing == []


def test_parse_origins_tolerates_real_world_values():
    from main import parse_origins
    assert parse_origins("https://drishti.vercel.app/") == ["https://drishti.vercel.app"]
    assert parse_origins(" https://a.com , http://localhost:5173/ ") == \
        ["https://a.com", "http://localhost:5173"]
    assert parse_origins(None) == ["http://localhost:5173"]
    assert parse_origins("") == ["http://localhost:5173"]
    assert parse_origins(",,") == ["http://localhost:5173"]


def test_dockerignore_excludes_heavy_and_secret_paths():
    di = open(os.path.join(SERVER, ".dockerignore")).read()
    for must in ("venv", "CubiCasa5k", "*.pkl", ".env", "tests"):
        assert must in di, f".dockerignore must exclude {must}"
