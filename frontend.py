import tkinter as tk
from PIL import Image, ImageTk, ImageSequence, ImageEnhance
import datetime
import socket
import threading
from itertools import cycle
from alen_backend import speak, listen, handle_pc_command, search_duckduckgo
from alen_backend import memory_response, teach_memory, log_interaction, predict_response_from_model
from alen_backend import apply_aliases

# === Theme Setup ===
current_theme = "dark"
themes = {
    "dark": {
        "bg": "#000000",
        "fg": "#ffffff",
        "entry_bg": "#1a1a1a",
        "chat_bg": "#181818",
        "status_fg": "#00ff00",
        "button_bg": "#1e88e5",
        "button_fg": "#ffffff"
    },
    "light": {
        "bg": "#f5f5f5",
        "fg": "#000000",
        "entry_bg": "#ffffff",
        "chat_bg": "#e0e0e0",
        "status_fg": "#2e7d32",
        "button_bg": "#42a5f5",
        "button_fg": "#ffffff"
    }
}

# === Functions ===
def send_message():
    user_input = entry.get()
    if not user_input.strip():
        return
    update_chat("You", user_input)
    entry.delete(0, tk.END)
    threading.Thread(target=process_message, args=(user_input, False)).start()


def process_message(user_input, is_voice=False):
    user_input = user_input.strip().lower()
    # 1. Check memory first
    memory = memory_response(user_input)
    if memory:
        response = memory
        update_chat("ALEN", response)
        if is_voice:
            speak(response)
        log_interaction(user_input, response, 0)
        show_feedback_buttons(user_input, response)
        return

    # 2. Check PC command
    response = handle_pc_command(user_input)
    if response:
        update_chat("ALEN", response)
        if is_voice:
            speak(response)
        log_interaction(user_input, response, 0)
        show_feedback_buttons(user_input, response)
        return

    # 3. Fallback to DuckDuckGo search
    if check_internet():
        # Try DuckDuckGo
        response = search_duckduckgo(user_input)
        if response and response != "Sorry, I couldn't find anything useful.":
            update_chat("ALEN", response)
            if is_voice:
                speak(response)
            log_interaction(user_input, response, 0)
            show_feedback_buttons(user_input, response)
            return
    

    # 4. Try RL model as fallback
    model_reply = predict_response_from_model(user_input)
    if model_reply:
        response = model_reply
        update_chat("ALEN (rl)", response)
        if is_voice:
            speak(response)
        log_interaction(user_input, response, 0)
        show_feedback_buttons(user_input, response)
        return

    # 5. Still no answer — ask user to teach
    response = "Sorry, I couldn't find anything useful."
    update_chat("ALEN", response)
    if is_voice:
        speak(response)
    log_interaction(user_input, response, 0)
    show_feedback_buttons(user_input, response)

    # Ask for user teaching
    def save_user_input():
        user_teach = teach_entry.get().strip()
        if user_teach:
            teach_memory(user_input, user_teach)
            update_chat("ALEN", "Thanks! I’ll remember that.")
            if is_voice:
                threading.Thread(target=lambda: speak("Thanks! I’ll remember that.")).start()
        teach_popup.destroy()

    teach_popup = tk.Toplevel(window)
    teach_popup.title("Teach ALEN")
    teach_popup.configure(bg="#1a1a1a")
    teach_popup.geometry("400x150")

    tk.Label(teach_popup, text="I didn't understand. Please teach me:", bg="#1a1a1a", fg="#ffffff").pack(pady=10)
    teach_entry = tk.Entry(teach_popup, width=50)
    teach_entry.pack(pady=5)
    tk.Button(teach_popup, text="Save", command=save_user_input).pack(pady=10)


def show_feedback_buttons(user_input, response):
    feedback_frame = tk.Frame(chat_log, bg="#000000")
    feedback_given = {"clicked": False}
    
    def mark_feedback(value):
        reward = 1 if value else -1
        feedback_given["clicked"] = True
        log_interaction(user_input, response, reward)
        feedback_frame.destroy()

    btn_style = {
        "bg": "#000000",
        "fg": "#ffffff",
        "activebackground": "#ffffff",  # white shiny effect on click
        "activeforeground": "#000000",  # text turns black when clicked
        "relief": "flat",
        "borderwidth": 0,
        "font": ("Arial", 10),
        "width": 2,
        "height": 1,
        "cursor": "hand2"  # finger pointer on hover
    }

    tk.Button(feedback_frame, text="👍", command=lambda: mark_feedback(True), **btn_style).pack(side=tk.LEFT, padx=2)
    tk.Button(feedback_frame, text="👎", command=lambda: mark_feedback(False), **btn_style).pack(side=tk.LEFT, padx=2)

    chat_log.config(state=tk.NORMAL)
    chat_log.window_create(tk.END, window=feedback_frame)
    chat_log.insert(tk.END, "\n\n")
    chat_log.config(state=tk.DISABLED)
    chat_log.see(tk.END)

    # Auto-log positive feedback after 8 seconds if no click
    def auto_log_if_no_feedback():
        if not feedback_given["clicked"]:
            log_interaction(user_input, response, 1)
            feedback_frame.destroy()

    feedback_frame.after(4000, auto_log_if_no_feedback)  # 8 seconds


def use_voice():
    threading.Thread(target=process_voice_command).start()

def process_voice_command():
    def handle_voice():
        command = listen()
        update_chat("You (voice)", command)
        threading.Thread(target=process_message, args=(command, True)).start()

    threading.Thread(target=handle_voice).start()


def update_chat(sender, message):
    chat_log.config(state=tk.NORMAL)
    timestamp = datetime.datetime.now().strftime("%H:%M")
    tag = "user" if sender.startswith("You") else "bot"

    formatted_message = f"{sender} ({timestamp}): {message}\n\n"
    chat_log.insert(tk.END, formatted_message, tag)
    chat_log.config(state=tk.DISABLED)
    chat_log.see(tk.END)


def style_button(btn, base_color="#1e88e5", hover_color="#1565c0"):
    def on_enter(e):
        btn.config(bg=hover_color, cursor="hand2")
    def on_leave(e):
        btn.config(bg=base_color)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.config(relief="flat", bd=0, highlightthickness=0)

def save_chat():
    with open("chat_history.txt", "w", encoding="utf-8") as f:
        f.write(chat_log.get("1.0", tk.END))

def check_internet():
    try:
        socket.create_connection(("1.1.1.1", 53))
        return True
    except OSError:
        return False

window = tk.Tk()
window.title("A L E N - Virtual Assistant")
window.configure(bg=themes[current_theme]["bg"])
window.geometry("900x1500")  # Fixed window size

main_frame = tk.Frame(window, bg=themes[current_theme]["bg"])
main_frame.pack(fill=tk.NONE, expand=False)  # Don't expand the frame

status_text = "Online ✅" if check_internet() else "Offline ❌"
status_label = tk.Label(main_frame, text=f"Status: {status_text}",
                        fg=themes[current_theme]["status_fg"], bg=themes[current_theme]["bg"],
                        font=("Segoe UI", 10, "bold"), anchor="e")
status_label.pack(anchor="ne", padx=10, pady=(10, 0))

# === ROUNDED BUTTON CLASS ===
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg, fg, font, width=120, height=40):
        super().__init__(parent, width=width, height=height, highlightthickness=0, bg=themes[current_theme]["bg"])
        
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
        self.hover_color = "#000066"  # optional: match your screenshot style
        self.font = font
        self.text = text
        self.width = width
        self.height = height
        self.radius = height // 2

        self.draw_button()
        self.bind_events()

    def draw_button(self):
        r = self.radius
        w = self.width
        h = self.height

        # Left and right rounded parts
        self.create_oval(0, 0, 2 * r, h, fill=self.bg_color, outline=self.bg_color)
        self.create_oval(w - 2 * r, 0, w, h, fill=self.bg_color, outline=self.bg_color)

        # Center rectangle
        self.create_rectangle(r, 0, w - r, h, fill=self.bg_color, outline=self.bg_color)

        # Button text
        self.text_id = self.create_text(w // 2, h // 2, text=self.text, fill=self.fg_color, font=self.font)

    def bind_events(self):
        self.tag_bind("all", "<Button-1>", lambda e: self.command())
        self.tag_bind("all", "<Enter>", lambda e: self.change_color(self.hover_color))
        self.tag_bind("all", "<Leave>", lambda e: self.change_color(self.bg_color))

    def change_color(self, color):
    # Only change color by redrawing once if necessary
        if hasattr(self, "current_color") and self.current_color == color:
            return  # No need to redraw
        self.current_color = color

        self.delete("all")
        r = self.radius
        w = self.width
        h = self.height
        self.create_oval(0, 0, 2 * r, h, fill=color, outline=color)
        self.create_oval(w - 2 * r, 0, w, h, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        self.text_id = self.create_text(w // 2, h // 2, text=self.text, fill=self.fg_color, font=self.font)



# === GIF HEADER ===
gif = Image.open("background.gif")
original_frames = [frame.copy().convert("RGBA") for frame in ImageSequence.Iterator(gif)]
frame_cycle = cycle(original_frames)

gif_frame = tk.Frame(main_frame, width=450, height=390, bg=themes[current_theme]["bg"])
gif_frame.pack_propagate(False)  # Prevent auto-resize
gif_frame.pack(padx=10, pady=(10, 0))


gif_label = tk.Label(gif_frame)
gif_label.pack(fill=tk.BOTH, expand=True)

def animate_gif():
    width = gif_frame.winfo_width()
    height = gif_frame.winfo_height()
    frame = next(frame_cycle)
    frame_resized = frame.resize((width, height), Image.LANCZOS)
    tk_frame = ImageTk.PhotoImage(frame_resized)
    gif_label.configure(image=tk_frame)
    gif_label.image = tk_frame
    window.after(100, animate_gif)

animate_gif()

# === CHAT AREA ===
# Wrapper frame to center the chat area
chat_wrapper = tk.Frame(main_frame, bg=themes[current_theme]["chat_bg"])
chat_wrapper.pack(pady=(5, 10), anchor="center")  # Center horizontally

# Chat canvas inside the wrapper
chat_canvas = tk.Canvas(chat_wrapper, width=800, height=420,
                        bg=themes[current_theme]["chat_bg"], highlightthickness=0, bd=0)
chat_canvas.pack()

# Chat log (Text widget) inside the canvas
chat_log = tk.Text(chat_canvas, bg="#000000", fg=themes[current_theme]["fg"],
                   font=("Consolas", 11), wrap=tk.WORD, state=tk.DISABLED,
                   bd=0, relief=tk.FLAT)

chat_log.tag_configure("user", justify="right", foreground="#ffffff", font=("Segoe UI", 11, "italic"))
chat_log.tag_configure("bot", justify="left", foreground="#ffffff", font=("Segoe UI", 11, "italic"))

# Add chat_log to canvas
chat_window = chat_canvas.create_window(0, 0, anchor='nw', window=chat_log, width=800, height=420)


chat_log.tag_configure("left", justify="left")
chat_log.tag_configure("right", justify="right")

# === ENTRY BOX ===

# Wrapper frame to center and size the entry box to 800px
entry_wrapper = tk.Frame(main_frame, width=800, height=35, bg=themes[current_theme]["entry_bg"])
entry_wrapper.pack(pady=(0, 10), anchor="center")  # Center horizontally
entry_wrapper.pack_propagate(False)  # Prevent auto-resizing

entry = tk.Entry(entry_wrapper, bg=themes[current_theme]["entry_bg"], fg=themes[current_theme]["fg"],
                 font=("Segoe UI", 12), insertbackground=themes[current_theme]["fg"],
                 bd=1, relief=tk.FLAT)
entry.pack(fill=tk.X, ipady=10)  # Add vertical padding

entry.bind("<Return>", lambda event: send_message())

# === BUTTONS ===
btn_frame = tk.Frame(main_frame, bg=themes[current_theme]["bg"])
btn_frame.pack(pady=(0, 10))

button_font = ("Segoe UI", 11, "bold")
bg_color = themes[current_theme]["button_bg"]
fg_color = themes[current_theme]["button_fg"]

send_btn = RoundedButton(btn_frame, text="Send", command=send_message, bg=bg_color, fg=fg_color, font=button_font)
send_btn.pack(side=tk.LEFT, padx=10)

voice_btn = RoundedButton(btn_frame, text="🎤 Voice", command=use_voice, bg=bg_color, fg=fg_color, font=button_font)
voice_btn.pack(side=tk.LEFT, padx=10)

save_btn = RoundedButton(btn_frame, text="💾 Save Chat", command=save_chat, bg=bg_color, fg=fg_color, font=button_font)
save_btn.pack(side=tk.LEFT, padx=10)


window.mainloop() 
