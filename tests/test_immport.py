import os , sys
sys.path.append(os.getcwd())
import pytest
from ThreadPoolExecutorPlus import *

@pytest.mark.asyncio
async def test_import():
    ThreadPoolExecutor()
    ...