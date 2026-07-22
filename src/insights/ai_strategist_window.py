"""
AI Race Strategist Window — Interactive chatbot that lets users ask
questions about the live race. Uses Google Gemini with full race-state
context to provide intelligent, data-driven answers.

Examples of questions users can ask:
  - "Why did Hamilton pit so early?"
  - "Who has the best chance of overtaking Verstappen?"
  - "Compare Norris and Piastri's tyre strategies"
  - "Should Leclerc switch to hards now?"
"""

from __future__ import annotations

import sys
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame, QSizePolicy,
    QTextEdit, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

from src.gui.pit_wall_window import PitWallWindow
from src.lib.settings import get_settings


# ── Driver code → surname map ───────────────────────────────────────────

DRIVER_NAMES = {
    "VER": "Verstappen", "HAM": "Hamilton", "NOR": "Norris",
    "LEC": "Leclerc", "SAI": "Sainz", "PIA": "Piastri",
    "RUS": "Russell", "PER": "Perez", "ALO": "Alonso",
    "STR": "Stroll", "GAS": "Gasly", "OCO": "Ocon",
    "HUL": "Hulkenberg", "MAG": "Magnussen", "TSU": "Tsunoda",
    "RIC": "Ricciardo", "ALB": "Albon", "SAR": "Sargeant",
    "BOT": "Bottas", "ZHO": "Zhou", "LAW": "Lawson",
    "COL": "Colapinto", "BEA": "Bearman", "DOO": "Doohan",
    "ANT": "Antonelli", "HAD": "Hadjar", "BOR": "Bortoleto",
}


STRATEGIST_SYSTEM_PROMPT = """\
You are an expert Formula 1 race strategist and analyst providing real-time
race insights via a chat interface embedded in a race replay tool.

Rules:
- Answer questions using ONLY the race data provided in the context. Never fabricate data.
- Be concise: 2–4 sentences for simple questions, up to a short paragraph for complex ones.
- Use driver surnames (e.g., "Verstappen"), not 3-letter codes.
- Reference specific data: lap numbers, tyre compounds, gaps, pit stop durations.
- Provide strategic reasoning when appropriate (undercuts, tyre cliffs, DRS trains, etc.).
- If the data doesn't contain enough information to answer, say so honestly.
- Do NOT use markdown formatting. Write plain text only.
- Be engaging — you're talking to an F1 fan who wants to understand the race better.

Driver code to name mapping:
VER=Verstappen, HAM=Hamilton, NOR=Norris, LEC=Leclerc, SAI=Sainz,
PIA=Piastri, RUS=Russell, PER=Perez, ALO=Alonso, STR=Stroll,
GAS=Gasly, OCO=Ocon, HUL=Hulkenberg, MAG=Magnussen, TSU=Tsunoda,
RIC=Ricciardo, ALB=Albon, SAR=Sargeant, BOT=Bottas, ZHO=Zhou,
LAW=Lawson, COL=Colapinto, BEA=Bearman, DOO=Doohan, ANT=Antonelli,
HAD=Hadjar, BOR=Bortoleto
"""


def _fmt_race_time(seconds: float) -> str:
    """Format session seconds as H:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02}:{s:02}"


def _friendly_api_error(e: Exception) -> str:
    """Convert a Groq API exception into a user-friendly message."""
    msg = str(e)
    if "429" in msg or "rate_limit_exceeded" in msg.lower():
        # Try to extract retry delay
        import re
        delay_match = re.search(r"retry in (\d+\.?\d*)s", msg, re.IGNORECASE)
        delay_str = f" Try again in {int(float(delay_match.group(1)))} seconds." if delay_match else ""
        return f"API rate limit hit.{delay_str} Please wait a moment and try again."
    if "401" in msg or "invalid_api_key" in msg.lower():
        return "Invalid API key. Check your Groq key in the settings."
    if "403" in msg:
        return "API key does not have permission."
    return f"API error: {msg[:200]}"


def _tyre_name(tyre_int) -> str:
    """Map numeric tyre compound id to human name."""
    from src.lib.tyres import TYRE_COMPOUND_NAMES
    try:
        return TYRE_COMPOUND_NAMES.get(int(tyre_int), "UNKNOWN")
    except (ValueError, TypeError):
        return "UNKNOWN"


def _driver_name(code: str) -> str:
    return DRIVER_NAMES.get(code, code)


# ── Chat message bubble ─────────────────────────────────────────────────

class ChatBubble(QFrame):
    """A single message bubble in the chat feed."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)

        if is_user:
            bg = "rgba(225, 6, 0, 0.12)"
            border_color = "rgba(225, 6, 0, 0.25)"
            text_color = "rgba(255, 255, 255, 0.95)"
            align = Qt.AlignRight
            label_text = "You"
            label_color = "#e10600"
        else:
            bg = "rgba(171, 71, 188, 0.10)"
            border_color = "rgba(171, 71, 188, 0.20)"
            text_color = "rgba(255, 255, 255, 0.92)"
            align = Qt.AlignLeft
            label_text = "🤖 AI Strategist"
            label_color = "#ab47bc"

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Sender label
        sender = QLabel(label_text)
        sender.setFont(QFont("Inter", 9, QFont.Bold))
        sender.setStyleSheet(f"color: {label_color}; border: none; background: transparent;")
        layout.addWidget(sender)

        # Message text
        msg = QLabel(text)
        msg.setFont(QFont("Inter", 12))
        msg.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(msg)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)


class TypingIndicator(QFrame):
    """Animated typing indicator shown while AI is generating a response."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: rgba(171, 71, 188, 0.06);
                border: 1px solid rgba(171, 71, 188, 0.12);
                border-radius: 10px;
                padding: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        self._label = QLabel("🤖 Thinking")
        self._label.setFont(QFont("Inter", 11))
        self._label.setStyleSheet("color: rgba(171, 71, 188, 0.7); border: none; background: transparent;")
        layout.addWidget(self._label)
        layout.addStretch()

        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(400)

    def _animate(self):
        self._dots = (self._dots + 1) % 4
        dots = "." * self._dots
        self._label.setText(f"🤖 Thinking{dots}")


# ── Main window ──────────────────────────────────────────────────────────

class AIStrategistWindow(PitWallWindow):
    """PitWallWindow subclass providing an interactive AI race strategist chat."""

    # Signal emitted from background thread to safely update UI
    _ai_response_ready = Signal(str)
    _ai_error = Signal(str)

    def __init__(self, auto_start_client: bool = True):
        # Race state tracking
        self._current_standings: list[dict] = []
        self._race_events: list[dict] = []
        self._current_lap: int = 0
        self._total_laps: int = 0
        self._session_time: float = 0
        self._track_status: str = ""
        self._weather: dict = {}
        self._conversation_history: list[dict] = []
        self._is_generating: bool = False

        super().__init__(auto_start_client=auto_start_client)
        self.setWindowTitle("🤖 AI Race Strategist")
        self.setGeometry(120, 80, 520, 750)

        # Connect signals
        self._ai_response_ready.connect(self._on_ai_response)
        self._ai_error.connect(self._on_ai_error)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #1a1a2e
                );
                border-bottom: 1px solid rgba(255,255,255,0.08);
            }
        """)
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title = QLabel("🤖 AI Race Strategist")
        title.setFont(QFont("Inter", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        h_layout.addWidget(title)

        subtitle = QLabel("Ask anything about the race — powered by Groq")
        subtitle.setFont(QFont("Inter", 11))
        subtitle.setStyleSheet("color: rgba(255,255,255,0.45);")
        h_layout.addWidget(subtitle)

        main_layout.addWidget(header)

        # ── Context status bar ─────────────────────────────────────────
        ctx_bar = QFrame()
        ctx_bar.setFixedHeight(32)
        ctx_bar.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
        """)
        ctx_layout = QHBoxLayout(ctx_bar)
        ctx_layout.setContentsMargins(16, 0, 16, 0)

        self.context_label = QLabel("Waiting for race data…")
        self.context_label.setFont(QFont("Inter", 10))
        self.context_label.setStyleSheet("color: rgba(255,255,255,0.4);")
        ctx_layout.addWidget(self.context_label)
        ctx_layout.addStretch()

        main_layout.addWidget(ctx_bar)

        # ── Chat feed (scrollable) ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.03); width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(14, 14, 14, 14)
        self.chat_layout.setSpacing(8)

        # Welcome message
        welcome = ChatBubble(
            "Hello! I'm your AI race strategist. Ask me anything about "
            "what's happening in the race — strategy calls, tyre performance, "
            "overtake chances, driver battles, and more. I'll use the live "
            "telemetry data to give you informed answers.",
            is_user=False
        )
        self.chat_layout.addWidget(welcome)
        self.chat_layout.addStretch()

        scroll.setWidget(self.chat_widget)
        self.scroll_area = scroll
        main_layout.addWidget(scroll, 1)

        # ── Suggested questions bar ────────────────────────────────────
        suggestions_frame = QFrame()
        suggestions_frame.setFixedHeight(44)
        suggestions_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.02);
                border-top: 1px solid rgba(255,255,255,0.04);
            }
        """)
        sug_layout = QHBoxLayout(suggestions_frame)
        sug_layout.setContentsMargins(10, 4, 10, 4)
        sug_layout.setSpacing(6)

        suggestions = [
            "Who's leading?",
            "Tyre strategies?",
            "Key battles?",
        ]
        for text in suggestions:
            btn = QPushButton(text)
            btn.setFont(QFont("Inter", 9))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.04);
                    color: rgba(255,255,255,0.5);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 14px;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background: rgba(171, 71, 188, 0.12);
                    color: rgba(255,255,255,0.8);
                    border-color: rgba(171, 71, 188, 0.3);
                }
            """)
            btn.clicked.connect(lambda checked, t=text: self._send_suggested(t))
            sug_layout.addWidget(btn)

        sug_layout.addStretch()
        main_layout.addWidget(suggestions_frame)

        # ── Input area ─────────────────────────────────────────────────
        input_frame = QFrame()
        input_frame.setFixedHeight(70)
        input_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border-top: 1px solid rgba(255,255,255,0.08);
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 10, 14, 10)
        input_layout.setSpacing(10)

        self.input_box = QTextEdit()
        self.input_box.setFont(QFont("Inter", 12))
        self.input_box.setPlaceholderText("Ask about the race…")
        self.input_box.setFixedHeight(44)
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: rgba(255,255,255,0.06);
                color: #e6edf3;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: rgba(171, 71, 188, 0.5);
            }
        """)
        self.input_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        input_layout.addWidget(self.input_box, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFont(QFont("Inter", 11, QFont.Bold))
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFixedSize(72, 44)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ab47bc, stop:1 #7b1fa2
                );
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ba68c8, stop:1 #8e24aa
                );
            }
            QPushButton:disabled {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.3);
            }
        """)
        self.send_btn.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.send_btn)

        main_layout.addWidget(input_frame)

        # ── Typing indicator (hidden by default) ───────────────────────
        self._typing_indicator: Optional[TypingIndicator] = None

        # ── Dark theme override ────────────────────────────────────────
        self.setStyleSheet(self.styleSheet() + """
            QMainWindow, QWidget { background: #0d1117; color: #e6edf3; }
        """)

    # ── Telemetry data handler ───────────────────────────────────────────

    def on_telemetry_data(self, data: dict):
        """Accumulate race state from each telemetry tick."""
        frame = data.get("frame", {})
        drivers = frame.get("drivers", {})

        if drivers:
            # Build standings
            standings = []
            for code, info in sorted(
                drivers.items(),
                key=lambda kv: kv[1].get("position", 99)
            ):
                standings.append({
                    "pos": info.get("position", "?"),
                    "driver": _driver_name(code),
                    "code": code,
                    "lap": info.get("lap", "?"),
                    "tyre": _tyre_name(info.get("tyre", 0)),
                    "tyre_life": int(info.get("tyre_life", 0)),
                    "in_pit": info.get("in_pit", False),
                    "speed": int(info.get("speed", 0)),
                })
            self._current_standings = standings

            # Extract current lap from leader
            if standings:
                self._current_lap = standings[0].get("lap", 0)

        # Track session time
        self._session_time = frame.get("t", self._session_time)

        # Total laps
        if "total_laps" in data:
            self._total_laps = data["total_laps"]

        # Track status — can arrive as a dict or a plain string
        ts = data.get("track_status", {})
        if ts:
            if isinstance(ts, dict):
                self._track_status = ts.get("message", str(ts.get("status", "")))
            else:
                self._track_status = str(ts)

        # Weather
        weather = frame.get("weather")
        if weather:
            self._weather = weather

        # Race events
        events = data.get("race_events", [])
        if events:
            self._race_events = events

        # Update context label
        if self._current_standings:
            leader = self._current_standings[0]
            ctx_text = f"Lap {self._current_lap}"
            if self._total_laps:
                ctx_text += f"/{self._total_laps}"
            ctx_text += f"  ·  Leader: {leader['driver']}"
            if self._track_status:
                ctx_text += f"  ·  {self._track_status}"
            self.context_label.setText(ctx_text)

    # ── Chat actions ─────────────────────────────────────────────────────

    def _send_suggested(self, text: str):
        """Handle a suggested question click."""
        self.input_box.setPlainText(text)
        self._on_send_clicked()

    def _on_send_clicked(self):
        """Handle send button click."""
        text = self.input_box.toPlainText().strip()
        if not text or self._is_generating:
            return

        # Add user bubble
        user_bubble = ChatBubble(text, is_user=True)
        idx = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(idx, user_bubble)

        # Clear input
        self.input_box.clear()

        # Show typing indicator
        self._show_typing()
        self._is_generating = True
        self.send_btn.setEnabled(False)

        # Build context + call Gemini in background thread
        context = self._build_race_context()
        self._conversation_history.append({"role": "user", "text": text})

        thread = threading.Thread(
            target=self._call_gemini,
            args=(text, context),
            daemon=True,
        )
        thread.start()

        # Auto-scroll
        QTimer.singleShot(100, self._scroll_to_bottom)

    def _show_typing(self):
        """Show the typing indicator in the chat."""
        self._typing_indicator = TypingIndicator()
        idx = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(idx, self._typing_indicator)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _hide_typing(self):
        """Remove the typing indicator."""
        if self._typing_indicator:
            self._typing_indicator.deleteLater()
            self._typing_indicator = None

    def _scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Context builder ──────────────────────────────────────────────────

    def _build_race_context(self) -> str:
        """Build a comprehensive text context of the current race state."""
        lines = []

        lines.append(f"=== CURRENT RACE STATE ===")
        lines.append(f"Lap: {self._current_lap}" +
                     (f" / {self._total_laps}" if self._total_laps else ""))
        lines.append(f"Race time: {_fmt_race_time(self._session_time)}")

        if self._track_status:
            lines.append(f"Track status: {self._track_status}")

        if self._weather:
            lines.append(
                f"Weather: Track {self._weather.get('track_temp', '?')}°C, "
                f"Air {self._weather.get('air_temp', '?')}°C"
            )

        # Standings
        if self._current_standings:
            lines.append("")
            lines.append("CURRENT STANDINGS:")
            for s in self._current_standings[:20]:
                pit_tag = " [IN PIT]" if s.get("in_pit") else ""
                lines.append(
                    f"  P{s['pos']} {s['driver']} ({s['code']}) — "
                    f"Lap {s['lap']}, {s['tyre']} tyres "
                    f"({s['tyre_life']}L old), {s['speed']}kph{pit_tag}"
                )

        # Recent events (last 15)
        if self._race_events:
            recent = [
                e for e in self._race_events
                if e.get("time", 0) <= self._session_time
            ][-15:]
            if recent:
                lines.append("")
                lines.append("RECENT RACE EVENTS:")
                for e in recent:
                    ai = e.get("ai_commentary", "")
                    template = e.get("commentary", "")
                    text = ai or template
                    lines.append(f"  Lap {e.get('lap', '?')}: [{e.get('type', '?')}] {text}")

        # Recent conversation for context continuity
        if self._conversation_history:
            lines.append("")
            lines.append("CONVERSATION SO FAR:")
            for msg in self._conversation_history[-6:]:
                role = "USER" if msg["role"] == "user" else "STRATEGIST"
                lines.append(f"  {role}: {msg['text'][:200]}")

        return "\n".join(lines)

    # ── Groq API call (runs in background thread) ──────────────────────

    def _call_gemini(self, user_question: str, context: str):
        """Call Groq API in background thread and emit result signal."""
        settings = get_settings()
        api_key = settings.groq_api_key
        model = settings.ai_model or "llama-3.3-70b-versatile"

        if not api_key:
            self._ai_error.emit(
                "No Groq API key configured. Go to Settings to add your key."
            )
            return

        user_prompt = (
            f"{context}\n\n"
            f"---\n"
            f"USER QUESTION: {user_question}\n\n"
            f"Answer the user's question using the race data above. "
            f"Be specific, reference actual data, and provide strategic insight."
        )

        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": STRATEGIST_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=400,
            )

            if response and response.choices and response.choices[0].message.content:
                text = response.choices[0].message.content.strip().replace("**", "").replace("*", "")
                self._ai_response_ready.emit(text)
            else:
                self._ai_error.emit("Groq returned an empty response.")

        except ImportError:
            self._ai_error.emit(
                "groq package not installed. Run: pip install groq"
            )
        except Exception as e:
            self._ai_error.emit(_friendly_api_error(e))

    # ── Signal handlers (run on UI thread) ───────────────────────────────

    def _on_ai_response(self, text: str):
        """Handle successful AI response — add bubble to chat."""
        self._hide_typing()
        self._is_generating = False
        self.send_btn.setEnabled(True)

        bubble = ChatBubble(text, is_user=False)
        idx = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(idx, bubble)

        self._conversation_history.append({"role": "assistant", "text": text})

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _on_ai_error(self, error_msg: str):
        """Handle AI error — show error bubble."""
        self._hide_typing()
        self._is_generating = False
        self.send_btn.setEnabled(True)

        error_bubble = ChatBubble(f"⚠️ {error_msg}", is_user=False)
        idx = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(idx, error_bubble)

        QTimer.singleShot(50, self._scroll_to_bottom)


# ── Standalone launch ────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    win = AIStrategistWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
