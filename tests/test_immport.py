import os , sys
o_path = os.getcwd()
sys.path.append(os.path.split(o_path)[0])
import pytest
from ThreadPoolExecutorPlus import *

async def test_import():
    ...