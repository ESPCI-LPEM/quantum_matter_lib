import os
import sys

from sphinx_pyproject import SphinxConfig

sys.path.insert(0, os.path.abspath('../..'))

config = SphinxConfig("../../pyproject.toml", globalns=globals())