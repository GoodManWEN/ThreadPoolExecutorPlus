import os , sys
sys.path.append(os.getcwd())
import pytest
from ThreadPoolExecutorPlus import *
import time

def test_feature():

    def some_func(arg):
        # does some heavy lifting
        # outputs some results
        time.sleep(arg)
        return arg

    def some_error():
        raise RuntimeError()

    with ThreadPoolExecutor() as executor:
        assert executor._max_workers >= executor._min_workers

        # test reuseability
        results = []
        _range = 10
        _sec = 0.5
        for _ in range(_range):
            results.append(executor.submit(some_func , _sec / 2))
            time.sleep(_sec)
            assert len(executor._threads) == min(_ + 1 , executor._min_workers)

        # test return
        results = list(map(lambda x:x.result() , results))
        assert results == [_sec / 2] * _range

        # test raise 
        result = executor.submit(some_error)
        time.sleep(_sec)
        assert result.done()
        assert isinstance(result.exception() , RuntimeError)

        # test opt
        _range2 = 2
        _range3 = 10
        _time2 = 5
        _sleeptime = 2
        _interval = 0.01
        _inaccuracy = 0.5
        executor.set_daemon_opts(min_workers = _range2 , max_workers = _range3 , keep_alive_time = _time2)
        assert executor._min_workers == _range2
        assert executor._max_workers == _range3
        assert executor._keep_alive_time == _time2

        # test execute
        results = []
        start_time = time.time()
        for _ in range(_range3):
            results.append(executor.submit(some_func , _sleeptime))
            time.sleep(_interval)

        list(map(lambda x:x.result() , results))
        end_time = time.time()
        assert (_sleeptime - _inaccuracy) <= (end_time - start_time) <= (_sleeptime * _range3 - _inaccuracy + _interval * _range3)

        # test shrink
        assert len(executor._threads) == _range3
        time.sleep(_time2 + _inaccuracy * 2)
        assert len(executor._threads) == _range2 or len(executor._threads) == (_range2 + 1)

        # test overflow
        _range4 = _range2 * 2
        _time3 = 0.5
        executor.set_daemon_opts(min_workers = _range2 , max_workers = _range2)
        results = []
        start_time = time.time()
        for _ in range(_range4):
            results.append(executor.submit(some_func , _time3))

        list(map(lambda x:x.result() , results))
        end_time = time.time()
        expect_time = (_time3 * _range4) / _range2
        assert (expect_time - _inaccuracy) <= (end_time - start_time) <= (expect_time + _inaccuracy)
