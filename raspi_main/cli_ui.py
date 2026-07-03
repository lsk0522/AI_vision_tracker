import sys
import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.status import Status

import state
import logger

# 원래 터미널 화면 출력을 보장하기 위해 sys.__stdout__ 사용
# (logger.py에서 sys.stdout을 가로채더라도 화면을 그릴 수 있어야 함)
_real_stdout = sys.__stdout__
console = Console(file=_real_stdout)

_live = None

def run_loading_sequence():
    """앱 시작 시 멋진 로딩 스피너 출력"""
    with Status("[bold magenta]::[/bold magenta] [white]Initializing AI Vision Tracker...[/white]", spinner="dots12", spinner_style="bold magenta", console=console) as status:
        time.sleep(0.8)
        status.update("[bold magenta]::[/bold magenta] [white]Checking Hardware (Camera and ESP32)...[/white]")
        time.sleep(1.0)
        status.update("[bold magenta]::[/bold magenta] [white]Loading OpenCV CSRT Tracker Model...[/white]")
        time.sleep(1.2)
        status.update("[bold magenta]::[/bold magenta] [white]Starting Flask Web Server...[/white]")
        time.sleep(0.5)

def generate_dashboard() -> Layout:
    """화면 갱신 시마다 호출되어 레이아웃(표+로그)을 반환"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=10),
        Layout(name="body")
    )
    
    # --- Status Table (상단) ---
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Component", style="cyan", width=20)
    table.add_column("Status", width=15)
    table.add_column("Details")
    
    # Motor Status
    motor_status = "[bold green]ONLINE[/]" if state.motor_connected else "[bold red]OFFLINE[/]"
    motor_info = f"Port: {state.motor_port} | Tgt: ({state.motor_target_x}, {state.motor_target_y})" if state.motor_connected else "Waiting for connection..."
    table.add_row("ESP32 Motors", motor_status, motor_info)
    
    # Camera Status
    cam_status = "[bold green]ONLINE[/]"
    fps_str = "Active" if getattr(state, 'current_frame', None) is not None else "No Feed"
    table.add_row("Vision System", cam_status, f"Feed: {fps_str} | Tracker: {state.tracking_mode}")
    
    # Operation Mode
    mode_str = "AUTO" if state.input_mode == "auto" else "MANUAL"
    table.add_row("System Mode", f"[bold yellow]{mode_str}[/]", f"Input: {state.input_mode}")

    layout["header"].update(Panel(table, title="[bold blue]AI Vision Tracker - Live Dashboard[/]", border_style="blue"))
    
    # --- Logs (하단) ---
    logs = logger.get_logs()
    # 로그 문자열을 합치고, Panel 안에 텍스트로 삽입
    log_text = Text.from_markup("\n".join(logs))
    layout["body"].update(Panel(log_text, title="[bold cyan]System Logs[/]", border_style="cyan"))
    
    return layout

def start_tui():
    """로거를 가로채고 TUI 대시보드 루프를 백그라운드로 시작"""
    global _live
    logger.setup_logger()
    # screen=True로 하면 별도의 화면 버퍼에서 돌아가므로 종료 시 원래 터미널 화면 복구됨
    # get_renderable 파라미터로 함수를 넘겨야 매 프레임마다 화면이 갱신됩니다.
    _live = Live(get_renderable=generate_dashboard, console=console, refresh_per_second=4, screen=True)
    _live.start()

def stop_tui():
    """TUI 대시보드 루프 종료"""
    global _live
    if _live:
        _live.stop()
