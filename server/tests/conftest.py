import os
import sys

# put the server/ folder on the path so `import main, perception` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
