import sys
import builtins
import logging
from collections import deque
from datetime import datetime
from rich.markup import escape

MAX_LOGS = 15
log_queue = deque(maxlen=MAX_LOGS)

class CustomStdout:
    def write(self, text):
        if text.strip():
            time_str = datetime.now().strftime("%H:%M:%S")
            log_queue.append(f"[dim]{time_str}[/dim] {escape(text.strip())}")
    def flush(self):
        pass
        
    # rich.console 호환성을 위한 isatty
    def isatty(self):
        return False

def setup_logger():
    # 1. 표준 출력(sys.stdout) 가로채기 (오류 메시지인 stderr는 화면에 그대로 출력되도록 둠)
    sys.stdout = CustomStdout()
    
    # 2. 내장 print() 함수 가로채기
    _original_print = builtins.print
    def custom_print(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        if text.strip():
            time_str = datetime.now().strftime("%H:%M:%S")
            log_queue.append(f"[dim]{time_str}[/dim] {escape(text.strip())}")
            
    builtins.print = custom_print

    # 3. 로깅(Waitress 등) 모듈 가로채기
    class QueueHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            time_str = datetime.now().strftime("%H:%M:%S")
            log_queue.append(f"[dim]{time_str}[/dim] [yellow]{escape(msg)}[/yellow]")
            
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    qh = QueueHandler()
    root_logger.addHandler(qh)

def get_logs():
    return list(log_queue)
