from rich.console import Console
from rich.status import Status
from rich.theme import Theme
import time

custom_theme = Theme({"info": "dim cyan", "warning": "magenta", "danger": "bold red"})
console = Console(theme=custom_theme)

def run_loading_sequence():
    # 'dots12' is similar to the pink braille/dot spinner
    with Status("[bold magenta]::[/bold magenta] [white]Initializing AI Vision Tracker...[/white]", spinner="dots12", spinner_style="bold magenta") as status:
        time.sleep(1.0)
        status.update("[bold magenta]::[/bold magenta] [white]Checking Hardware (Camera and ESP32)...[/white]")
        time.sleep(1.2)
        status.update("[bold magenta]::[/bold magenta] [white]Loading OpenCV CSRT Tracker Model...[/white]")
        time.sleep(1.5)
        status.update("[bold magenta]::[/bold magenta] [white]Starting Flask Web Server...[/white]")
        time.sleep(1.0)
    


if __name__ == "__main__":
    run_loading_sequence()
