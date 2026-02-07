import sys

class TerminalDisplay:
    """
    Handles real-time terminal-based streaming updates for transcription.
    """
    
    def __init__(self):
        self.last_text = ""
        self.max_line_length = 0

    def update(self, text: str):
        """
        Updates the current line with streaming text.
        """
        # Clear previous line if new text is shorter
        padding = " " * max(0, self.max_line_length - len(text))
        sys.stdout.write(f"\r{text}{padding}")
        sys.stdout.flush()
        
        self.last_text = text
        self.max_line_length = max(self.max_line_length, len(text))

    def finalize(self, text: str):
        """
        Finalizes the current line and moves to the next one.
        """
        padding = " " * max(0, self.max_line_length - len(text))
        sys.stdout.write(f"\r{text}{padding}\n")
        sys.stdout.flush()
        
        self.last_text = ""
        self.max_line_length = 0