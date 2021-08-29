# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Implements ThreadPoolExecutor."""

__author__ = 'WEN (github.com/GoodManWEN)'
__original_author__ = 'Brian Quinlan (brian@sweetapp.com)'

import atexit
from concurrent.futures import _base
import itertools
import queue
import threading
import weakref
import os
import platform

pltfm = platform.system()
if pltfm == 'Windows':
    DEFAULT_MAXIMUM_WORKER_NUM = (os.cpu_count() or 1) * 16
elif pltfm == 'Linux' or pltfm == 'Darwin':
    DEFAULT_MAXIMUM_WORKER_NUM = (os.cpu_count() or 1) * 32
else:
    raise RuntimeError("We havent decided how many threads should acquire on your platform. Maybe you have to modify source code your self.")

BASE_ABOVE_PY_37 = True if 'BrokenExecutor' in dir(_base) else False
QUEUE_ABOVE_PY_37 = True if 'SipleQueue' in dir(queue) else False

# Workers are created as daemon threads. This is done to allow the interpreter
# to exit when there are still idle threads in a ThreadPoolExecutor's thread
# pool (i.e. shutdown() was not called). However, allowing workers to die with
# the interpreter has two undesirable properties:
#   - The workers would still be running during interpreter shutdown,
#     meaning that they would fail in unpredictable ways.
#   - The workers could be killed while evaluating a work item, which could
#     be bad if the callable being evaluated has external side-effects e.g.
#     writing to a file.
#
# To work around this problem, an exit handler is installed which tells the
# workers to exit when their work queues are empty and then waits until the
# threads finish.

_threads_queues = weakref.WeakKeyDictionary()
_shutdown = False


def _python_exit():
    global _shutdown
    _shutdown = True
    items = list(_threads_queues.items())
    for t, q in items:
        q.put(None)
    for t, q in items:
        t.join()


atexit.register(_python_exit)


class _WorkItem(object):
    def __init__(self, future, fn, args, kwargs):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return

        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Break a reference cycle with the exception 'exc'
            self = None
        else:
            self.future.set_result(result)


class _CustomThread(threading.Thread):

    def __init__(self , name , executor_reference, work_queue, initializer, initargs , thread_counter):
        super().__init__(name = name)
        self._executor_reference = executor_reference
        self._work_queue = work_queue
        self._initializer = initializer
        self._initargs = initargs
        self._executor = executor_reference()
        self._thread_count_id = thread_counter

    def run(self):
        if self._initializer is not None:
            try:
                self._initializer(*self._initargs)
            except BaseException:
                _base.LOGGER.critical('Exception in initializer:', exc_info=True)
                executor = self._executor_reference()
                if executor is not None:
                    executor._initializer_failed()
                return

        try:
            self._executor._adjust_free_thread_count(1)
            while True:
                try:
                    work_item = self._work_queue.get(block=True , timeout = self._executor._keep_alive_time)
                except queue.Empty:
                    '''
                    A bug may cause potential risk here.

                    Simply put, cause unrigister queue listening (adjust free thread count -= 1) is not atomic operation after 
                    exception thrown, thus there's slightly chance thread swtiching (which is controled by os and not going to be 
                    interfered by user) happens just right the time after listening stopped but before free thread count is adjusted.

                    At that precisely time point , if there's a new task going to be added in main thread , determine statement  
                    in ThreadPoolExecutor._adjust_thread_count would consider mistakenly there's still enough worker listening ,
                    and decide not to generate a new thread. That may eventually cause a final result of task added in queue
                    but no worker takes it out in the meantime. The last task will never run if there's no new tasks trigger ThreadPoolExecutor._adjust_thread_count afterwards.

                    To fix this problem , the most reasonable , yes high cost , solution would be hacking into cpython's queue 
                    module (which was a .pyd file projected to 'Modules/_queuemodule.c' in source code) , makes 
                    self._executor._free_thread_count adjusted before listening suspended in interrupt of timeout's callback 
                    functions.

                    If that sounds a little bit hard to implement , the alternatively simplified approach would be preserving 
                    serveral 'core thread' which would still looping in timeout but never halt , with the same quantity as 
                    ThreadPoolExecutor.min_workers.

                    Based on this implementation , the status refresh not in time bug will still occur whereas there's always 
                    sub-threads working to trigger task out of task queue. This may cause sub-threads block , which was slightly
                    out of line with expectations, at some paticular situation if existing threads occasionally full loaded.
                    With another potential symptom is , depends on which task was last triggered by system, size of thread 
                    pool may not be precisely the same as expect just right after thread shrink happened.
                    '''
                    if self._thread_count_id < self._executor._min_workers:
                        continue

                    with self._executor._free_thread_count_lock:
                        if self._executor._free_thread_count > self._executor._min_workers:
                            self._executor._free_thread_count -= 1
                            break
                        else:
                            continue

                if work_item is not None:
                    self._executor._adjust_free_thread_count(-1)
                    work_item.run()
                    # Delete references to object. See issue16284
                    del work_item
                    self._executor._adjust_free_thread_count(1)
                    continue
                executor = self._executor_reference()
                # Exit if:
                #   - The interpreter is shutting down OR
                #   - The executor that owns the worker has been collected OR
                #   - The executor that owns the worker has been shutdown.
                if _shutdown or executor is None or executor._shutdown:
                    # Flag the executor as shutting down as early as possible if it
                    # is not gc-ed yet.
                    if executor is not None:
                        executor._shutdown = True
                    # Notice other workers
                    self._work_queue.put(None)
                    return
                del executor
        except BaseException:
            _base.LOGGER.critical('Exception in worker', exc_info=True)



class _CustomWeakSet(weakref.WeakSet):

    def __repr__(self):
        return repr(self.data)


class BrokenExecutor(RuntimeError):
    """
    Raised when a executor has become non-functional after a severe failure.
    """

# Upward Compatible
_class_brokenexecutor = _base.BrokenExecutor if BASE_ABOVE_PY_37 else BrokenExecutor


class BrokenThreadPool(_class_brokenexecutor):
    """
    Raised when a worker thread in a ThreadPoolExecutor failed initializing.
    """


class ThreadPoolExecutor(_base.Executor):

    # Used to assign unique thread names when thread_name_prefix is not supplied.
    _counter = itertools.count().__next__

    def __init__(self, max_workers=None, thread_name_prefix='',
                 initializer=None, initargs=()):
        """Initializes a new ThreadPoolExecutor instance.

        Args:
            max_workers: The maximum number of threads that can be used to
                execute the given calls.
            thread_name_prefix: An optional name prefix to give our threads.
            initializer: An callable used to initialize worker threads.
            initargs: A tuple of arguments to pass to the initializer.
        """
        self._min_workers = 4
        self._keep_alive_time = 100
        if max_workers is None:
            # Use this number because ThreadPoolExecutor is often
            # used to overlap I/O instead of CPU work.
            max_workers = DEFAULT_MAXIMUM_WORKER_NUM
        if max_workers < 1:
            raise ValueError("max_workers must be greater than min_workers , min_workers must be greater than 1")
        elif 1 <= max_workers < self._min_workers:
            self._min_workers = max_workers

        if initializer is not None and not callable(initializer):
            raise TypeError("initializer must be a callable")

        self._max_workers = max_workers
        self._work_queue = queue.SimpleQueue() if QUEUE_ABOVE_PY_37 else queue.Queue(max_workers << 6)
        self._threads = _CustomWeakSet()
        self._broken = False
        self._shutdown = False
        self._shutdown_lock = threading.RLock()
        self._free_thread_count = 0
        self._free_thread_count_lock = threading.RLock()
        self._thread_name_prefix = (thread_name_prefix or
                                    ("ThreadPoolExecutor-%d" % self._counter()))
        self._initializer = initializer
        self._initargs = initargs
        self._thread_counter = 0

    def set_daemon_opts(self , min_workers = None, max_workers = None, keep_alive_time = None):
        if min_workers is not None and min_workers < 1:
            raise ValueError('min_workers is not allowed to set below 1')
        if max_workers is not None and max_workers < min_workers:
            raise ValueError('max_workers is not allowed to set below min_workers')
        if min_workers is not None:
            self._min_workers = min_workers
        if max_workers is not None:
            self._max_workers = max_workers
        if keep_alive_time is not None:
            self._keep_alive_time = keep_alive_time

    def submit(self, fn, *args, **kwargs):
        with self._shutdown_lock:
            if self._broken:
                raise BrokenThreadPool(self._broken)

            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')
            if _shutdown:
                raise RuntimeError('cannot schedule new futures after'
                                   'interpreter shutdown')

            f = _base.Future()
            w = _WorkItem(f, fn, args, kwargs)

            self._work_queue.put(w)
            self._adjust_thread_count()
            return f
    submit.__doc__ = _base.Executor.submit.__doc__

    def _adjust_thread_count(self):
        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        def weakref_cb(_, q=self._work_queue):
            q.put(None)
        # TODO(bquinlan): Should avoid creating new threads if there are more
        # idle threads than items in the work queue.
        num_threads = len(self._threads)
        
        with self._free_thread_count_lock:
            _tflag = True if self._free_thread_count < self._min_workers else False
                
        if _tflag and num_threads < self._max_workers:
            thread_name = '%s_%d' % (self._thread_name_prefix or self,
                                     num_threads)
            t = _CustomThread(name=thread_name, 
                               executor_reference = weakref.ref(self, weakref_cb), 
                               work_queue = self._work_queue, 
                               initializer = self._initializer, 
                               initargs = self._initargs,
                               thread_counter = self._thread_counter
                )
            t.daemon = True
            t.start()
            self._threads.add(t)
            _threads_queues[t] = self._work_queue
            self._thread_counter += 1

    def _adjust_free_thread_count(self , num):
        with self._free_thread_count_lock:
            self._free_thread_count += num

    def _initializer_failed(self):
        with self._shutdown_lock:
            self._broken = ('A thread initializer failed, the thread pool '
                            'is not usable anymore')
            # Drain work queue and mark pending futures failed
            while True:
                try:
                    work_item = self._work_queue.get_nowait()
                except queue.Empty:
                    break
                if work_item is not None:
                    work_item.future.set_exception(BrokenThreadPool(self._broken))

    def _remove_thread(self , target):
        self._threads.remove(target)
        _threads_queues.pop(target)
        del target

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            self._shutdown = True
            self._work_queue.put(None)
        if wait:
            for t in self._threads:
                t.join()
    shutdown.__doc__ = _base.Executor.shutdown.__doc__
