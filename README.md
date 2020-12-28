# ThreadPoolExecutorPlus
[![fury](https://badge.fury.io/py/ThreadPoolExecutorPlus.svg)](https://badge.fury.io/py/ThreadPoolExecutorPlus)
[![licence](https://img.shields.io/github/license/GoodManWEN/ThreadPoolExecutorPlus)](https://github.com/GoodManWEN/ThreadPoolExecutorPlus/blob/master/LICENSE)
[![pyversions](https://img.shields.io/pypi/pyversions/ThreadPoolExecutorPlus.svg)](https://pypi.org/project/ThreadPoolExecutorPlus/)
[![Publish](https://github.com/GoodManWEN/ThreadPoolExecutorPlus/workflows/Publish/badge.svg)](https://github.com/GoodManWEN/ThreadPoolExecutorPlus/actions?query=workflow:Publish)
[![Build](https://github.com/GoodManWEN/ThreadPoolExecutorPlus/workflows/Build/badge.svg)](https://github.com/GoodManWEN/ThreadPoolExecutorPlus/actions?query=workflow:Build)

This package provides you a duck typing of concurrent.futures.ThreadPoolExecutor , which has the very similar api and could fully replace ThreadPoolExecutor in your code.

The reason why this pack exists is we would like to solve several specific pain spot in native python library of memory control.

## Feature
- Fully replaceable with concurrent.futures.ThreadPoolExecutor , for example in asyncio.
- Whenever submit a new task , executor will perfer to use existing idle thread rather than create a new one.
- Executor will automatically shrink itself duriung leisure time in order to achieve less memory and higher efficiency.

## Install

    pip install ThreadPoolExecutorPlus

## Usage
Same api as concurrent.futures.ThreadPoolExecutor , with some more control function added.

##### set_daemon_opts(min_workers = None, max_workers = None, keep_alive_time = None)
    
&emsp;&emsp;&emsp; In order to guarantee same api interface , new features should be modfied after object created.  
&emsp;&emsp;&emsp; Could change minimum/maximum activate worker num , and set after how many seconds will the  
&emsp;&emsp;&emsp; idle thread terminated.   
&emsp;&emsp;&emsp; By default , min_workers = 4 , max_workers = 16 times cpu_core count on windows and 32x on  
&emsp;&emsp;&emsp; linux , keep_alive_time = 100s. 

## Example

Very the same code in official doc [#threadpoolexecutor-example](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor-example) , with executor replaced:
```Python3
# requests_test.py
import concurrent.futures
import ThreadPoolExecutorPlus
import urllib.request

URLS = ['http://www.foxnews.com/',
        'http://www.cnn.com/',
        'http://europe.wsj.com/',
        'http://www.bbc.co.uk/',
        'http://some-made-up-domain.com/']

def load_url(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as conn:
        return conn.read()

with ThreadPoolExecutorPlus.ThreadPoolExecutor(max_workers=5) as executor:
    # Try modify deamon options
    executor.set_daemon_opts(min_workers = 2 , max_workers = 10 , keep_alive_time = 60)
    future_to_url = {executor.submit(load_url, url, 60): url for url in URLS}
    for future in concurrent.futures.as_completed(future_to_url):
        url = future_to_url[future]
        try:
            data = future.result()
        except Exception as exc:
            print('%r generated an exception: %s' % (url, exc))
        else:
            print('%r page is %d bytes' % (url, len(data)))
```

Same code in offcial doc [#executing-code-in-thread-or-process-pools](https://docs.python.org/3/library/asyncio-eventloop.html#executing-code-in-thread-or-process-pools) with executor replaced:
```Python3
# Runs on python version above 3.7
import asyncio
import concurrent.futures
import ThreadPoolExecutorPlus

def blocking_io():
    with open('/dev/urandom', 'rb') as f:
        return f.read(100)

def cpu_bound():
    return sum(i * i for i in range(10 ** 7))

async def main():
    loop = asyncio.get_running_loop()

    with ThreadPoolExecutorPlus.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(
            pool, blocking_io)
        print('custom thread pool', result)

asyncio.run(main())
```


