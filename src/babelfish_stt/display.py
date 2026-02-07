import sys

class TerminalDisplay:
    """
    Handles real-time terminal-based streaming updates for transcription.
    """
    
    def __init__(self):
        self.last_text = ""
        self.max_line_length = 0

    def update(self, text: str = "", refined: str = "", ghost: str = ""):
        """
        Updates the current line with streaming text.
        Supports ANSI styles: Refined is Bold, Ghost is Dimmed.
        """
        if refined or ghost:
            # ANSI escape codes: 1=Bold, 2=Dim, 0=Reset
            display_text = ""
            if refined:
                display_text += f"\033[1m{refined}\033[0m"
            if ghost:
                separator = " " if refined else ""
                display_text += f"{separator}\033[2m{ghost}\033[0m"
            
            # For length tracking, we need to ignore ANSI codes
            plain_text = (refined + (" " if refined and ghost else "") + ghost).strip()
        else:
            display_text = text
            plain_text = text

        # Clear previous line if new text is shorter
        padding = " " * max(0, self.max_line_length - len(plain_text))
        sys.stdout.write(f"\r{display_text}{padding}")
        sys.stdout.flush()
        
        self.last_text = plain_text
        self.max_line_length = max(self.max_line_length, len(plain_text))

    def finalize(self, text: str = ""):
        """
        Finalizes the current line and moves to the next one (bold).
        """
        # ANSI escape codes: 1=Bold, 0=Reset
        display_text = f"\033[1m{text}\033[0m"
        
        padding = " " * max(0, self.max_line_length - len(text))
        sys.stdout.write(f"\r{display_text}{padding}\n")
        sys.stdout.flush()
        
        self.last_text = ""
        self.max_line_length = 0