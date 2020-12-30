import os , sys
sys.path.append(os.getcwd())
import pytest
from ThreadPoolExecutorPlus import *
import concurrent.futures
import urllib.request
import asyncio
pltfm = platform.system()
WIN_RUNNING = False
if pltfm == 'Windows':
    WIN_RUNNING = True

def test_threadpoolexecutor_example():
    URLS = [
        'http://www.foxnews.com/',
        'http://www.cnn.com/',
        'http://europe.wsj.com/',
        'http://www.bbc.co.uk/',
        'http://www.google.com/',
        'http://www.youtube.com/'
    ]

    def load_url(url, timeout):
        with urllib.request.urlopen(url, timeout=timeout) as conn:
            return conn.read()

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_url = {executor.submit(load_url, url, 60): url for url in URLS}
        succeed_count = 0
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception as exc:
                pass
            else:
                assert len(data) > 0
                succeed_count += 1
        assert succeed_count > 0

@pytest.mark.asyncio
async def test_executing_code_in_thread_or_process_pools():

    def blocking_io():
        if WIN_RUNNING:
            return
        with open('/dev/urandom', 'rb') as f:
            return f.read(100)

    def cpu_bound():
        return sum(i * i for i in range(2 * 10 ** 6))

    loop = asyncio.get_running_loop() if 'get_running_loop' in dir(asyncio) else asyncio.get_event_loop()

    with ThreadPoolExecutor() as pool:
        result1 = await loop.run_in_executor(pool, blocking_io)
        result2 = await loop.run_in_executor(pool, cpu_bound)
        assert len(result1) == 100
        assert result2 == 2666664666667000000
