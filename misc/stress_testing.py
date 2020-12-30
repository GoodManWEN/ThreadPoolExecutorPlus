from ThreadPoolExecutorPlus import ThreadPoolExecutor
from collections import deque
import time
import random
import datetime
import asyncio
import os
import platform
pltfm = platform.system()

'''
Significantly performace drop down found on linux , reason not clear.
'''

def func(arg):
    time.sleep(arg)
    return str(arg)

async def one_task(loop , executor , arg , statistics , dataflow):
    r = await loop.run_in_executor(executor , func , arg)
    if r == str(arg):
        statistics[0] += 1
        statistics[2] += arg
    else:
        statistics[1] += 1
    dataflow[0] = dataflow[0] - arg

async def report_thread(executor , statistics , dataflow  , scale_factor):
    st = time.time()
    line = deque()
    while True:
        await asyncio.sleep(2)
        print(f"Report every 2 secs : [success] {statistics[0]} \t[fail] {statistics[1]} \t[dataflow] {'%.2f' % round(dataflow[0],2)} \t[currentthread] {len(executor._threads)} \t[qps] {round((statistics[0] / (time.time() - st)) , 2)}")

async def main():
    loop = asyncio.get_running_loop()
    statistics = [0 , 0 , 0]
    dataflow = [0]
    max_capability = 1024 * 10 * 0.8
    scale_factor = 0.2
    if pltfm == 'Windows':
        max_workers = min((os.cpu_count() or 1) << 7 , 1024)
    elif pltfm == 'Linux' or pltfm == 'Darwin':
        max_workers = min((os.cpu_count() or 1) << 8 , 4096)
    else:
        raise RuntimeError('could only run on x86 platform')

    with ThreadPoolExecutor(max_workers = max_workers) as executor:
        loop.create_task(report_thread(executor , statistics , dataflow , scale_factor))
        while True:
            rand_time = random.random() * scale_factor
            if dataflow[0] >= max_capability:
                await asyncio.sleep(0.1)
                continue
            # else:
            dataflow[0] = dataflow[0] + rand_time
            loop.create_task(one_task(loop , executor , rand_time , statistics , dataflow))
            await asyncio.sleep(0.001)

asyncio.run(main())
