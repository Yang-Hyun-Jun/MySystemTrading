from concurrent.futures import thread
from distutils.log import Log
import queue
import threading
from .log_manager import LogManager

class Worker:
    """
    입력받은 task를 별도의 thread에서 차례대로 수행시키는 모듈

    task가 추가되면 차례대로 task를 수행한다.    
    task는 딕셔너리이며 runnable에는 실행 가능한 객체를 담고 있어야 하며
    runnable의 인자로 task를 넘겨준다. 
    """
    
    def __init__(self, name):
        self.task_queue = queue.Queue()
        self.thread = None
        self.logger = LogManager.get_logger(name)

    def post_task(self, task):
        """
        task를 추가한다. 
        
        task: 
        딕셔너리이며 runnable에는 실행 가능한 객체를 담고 있다. 
        runnable의 인자로 task를 넘겨준다. 
        """
        self.task_queue.put(task)

    def start(self):
        """
        작업을 수행할 스레드를 만들고 start한다. 
        이미 작업이 진행되고 있는 경우 아무런 일도 일어나지 않는다. 
        """

        if self.thread is not None:
            return
        
        def looper():
            while True:
                task = self.task_queue.get()

                if task is None:
                    self.task_queue.task_done()
                    break

                runnable = task["runnable"]
                runnable(task)
                self.task_queue.task_done()
            
        self.thread = threading.Thread(target=looper, daemon=True)
        self.thread.start()
            
    def stop(self):
        """ 현재 진행 중인 작업을 끝으로 쓰레드를 종료 """
        if self.thread is None:
            return

        self.task_queue.put(None)
        self.thread = None
        self.task_queue.join()

