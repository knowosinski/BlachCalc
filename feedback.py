import re
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any
from urllib.parse import urlencode

from dashboard_shared import ACCENT, BACKGROUND, BORDER, INK, WHITE, theme_color
from feedback_store import FeedbackWorkbook, feedback_workbook_path


FEEDBACK_RECIPIENT = "k.nowosinski@izotechnika-cnc.pl"
FEEDBACK_CATEGORIES = ("Błąd", "Propozycja", "Ulepszenie", "Inne")
MAX_FEEDBACK_LENGTH = 5000


def _app_color(app: Any, color: str) -> str:
    return theme_color(color, app._dark_mode, app._theme_settings)


class FeedbackDialog:
    def __init__(self, app: Any, workbook_path: str | Path | None = None) -> None:
        self.app = app
        self.feedback_workbook = FeedbackWorkbook(workbook_path or feedback_workbook_path())
        self.dialog = tk.Toplevel(app)
        self.dialog.title("Feedback do BlachCalc")
        self.dialog.transient(app)
        self.dialog.configure(background=_app_color(app, BACKGROUND))
        self.dialog.resizable(True, True)
        width = min(680, max(1, app.winfo_screenwidth() - 40))
        height = min(620, max(1, app.winfo_screenheight() - 80))
        self.dialog.minsize(min(560, width), min(480, height))
        x = max(0, (app.winfo_screenwidth() - width) // 2)
        y = max(0, (app.winfo_screenheight() - height) // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        self.dialog.grab_set()

        self.author_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.category_var = tk.StringVar(value=FEEDBACK_CATEGORIES[0])
        self._build()

    def _build(self) -> None:
        content = ttk.Frame(self.dialog, padding=24)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Przekaż feedback", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            content,
            text=(
                "Zgłoszenie zostanie zapisane lokalnie, a następnie otworzymy "
                f"szkic wiadomości do {FEEDBACK_RECIPIENT}."
            ),
            style="Subtitle.TLabel",
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(3, 14))

        form = ttk.Frame(content, style="Card.TFrame", padding=18)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Imię i nazwisko *", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.author_entry = ttk.Entry(form, textvariable=self.author_var)
        self.author_entry.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(form, text="E-mail do kontaktu (opcjonalnie)", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Entry(form, textvariable=self.email_var).grid(
            row=3, column=0, sticky="ew", pady=(0, 12)
        )
        ttk.Label(form, text="Rodzaj zgłoszenia", style="Card.TLabel").grid(
            row=4, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Combobox(
            form,
            textvariable=self.category_var,
            values=FEEDBACK_CATEGORIES,
            state="readonly",
        ).grid(row=5, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(form, text="Opis *", style="Card.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 5)
        )
        message_frame = ttk.Frame(form, style="Card.TFrame")
        message_frame.grid(row=7, column=0, sticky="nsew")
        self.message_text = tk.Text(
            message_frame,
            height=8,
            wrap="word",
            undo=True,
            background=_app_color(self.app, WHITE),
            foreground=_app_color(self.app, INK),
            insertbackground=_app_color(self.app, INK),
            highlightthickness=1,
            highlightbackground=_app_color(self.app, BORDER),
            highlightcolor=_app_color(self.app, ACCENT),
            relief="flat",
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(message_frame, command=self.message_text.yview)
        self.message_text.configure(yscrollcommand=scrollbar.set)
        self.message_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        ttk.Label(
            form,
            text="E-mail autora zostanie dołączony do wiadomości jako dane kontaktowe.",
            style="CardMuted.TLabel",
            wraplength=600,
        ).grid(row=8, column=0, sticky="w", pady=(8, 0))
        form.columnconfigure(0, weight=1)
        form.rowconfigure(7, weight=1)

        actions = ttk.Frame(content)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Anuluj", command=self.dialog.destroy).pack(side="right")
        ttk.Button(
            actions,
            text="Zapisz i utwórz szkic e-maila",
            style="Primary.TButton",
            command=self.submit,
        ).pack(side="right", padx=(0, 8))
        self.author_entry.focus_set()
        self.dialog.bind("<Escape>", lambda event: event.widget.destroy())

    def submit(self) -> None:
        author = self.author_var.get().strip()
        email = self.email_var.get().strip()
        category = self.category_var.get().strip()
        message = self.message_text.get("1.0", "end-1c").strip()
        if not author:
            messagebox.showerror(
                "Feedback",
                "Wpisz imię i nazwisko.",
                parent=self.dialog,
            )
            return
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            messagebox.showerror(
                "Feedback",
                "Podaj poprawny adres e-mail albo pozostaw pole puste.",
                parent=self.dialog,
            )
            return
        if not message:
            messagebox.showerror(
                "Feedback",
                "Wpisz opis zgłoszenia.",
                parent=self.dialog,
            )
            return
        if len(message) > MAX_FEEDBACK_LENGTH:
            messagebox.showerror(
                "Feedback",
                f"Opis nie może przekraczać {MAX_FEEDBACK_LENGTH} znaków.",
                parent=self.dialog,
            )
            return

        try:
            feedback_id, created_at = self.feedback_workbook.append(
                author,
                email,
                category,
                message,
            )
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Nie udało się zapisać feedbacku",
                str(error),
                parent=self.dialog,
            )
            return

        email_body = (
            f"Zgłoszenie BlachCalc nr {feedback_id}\n"
            f"Autor: {author}\n"
            f"E-mail kontaktowy: {email or 'nie podano'}\n"
            f"Kategoria: {category}\n"
            f"Data i godzina: {created_at}\n\n"
            f"{message}"
        )
        mailto = "mailto:" + FEEDBACK_RECIPIENT + "?" + urlencode({
            "subject": f"Feedback BlachCalc — {category}",
            "body": email_body,
        })
        try:
            opened = webbrowser.open(mailto)
        except (OSError, webbrowser.Error) as error:
            opened = False
            mail_error = str(error)
        else:
            mail_error = ""

        if opened:
            messagebox.showinfo(
                "Feedback zapisany",
                f"Zgłoszenie zapisano w pliku Excel:\n{self.feedback_workbook.path}\n\n"
                "Sprawdź szkic w programie pocztowym i wyślij go, aby przekazać feedback.",
                parent=self.dialog,
            )
        else:
            messagebox.showwarning(
                "Feedback zapisany",
                "Zgłoszenie zapisano w pliku Excel, ale nie udało się otworzyć szkicu. "
                f"Możesz wysłać wiadomość ręcznie na {FEEDBACK_RECIPIENT}."
                + (f"\n\n{mail_error}" if mail_error else ""),
                parent=self.dialog,
            )
        self.dialog.destroy()
