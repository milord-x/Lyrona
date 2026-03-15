from __future__ import annotations

import os
import select
import shutil
import sys
import termios
import tty
import unicodedata
from typing import Generic, List, Optional, Sequence, Tuple, TypeVar


T = TypeVar("T")


def _char_width(char: str) -> int:
    if not char:
        return 0
    if char in {"\n", "\r"}:
        return 0
    if unicodedata.combining(char):
        return 0
    if unicodedata.category(char) == "Cf":
        return 0
    if unicodedata.east_asian_width(char) in {"W", "F"}:
        return 2
    return 1


def _text_width(text: str) -> int:
    return sum(_char_width(char) for char in text)


def _truncate_text(text: str, width: int) -> str:
    if width <= 0:
        return ""

    cells = 0
    buffer: List[str] = []

    for char in text:
        char_cells = _char_width(char)
        if cells + char_cells > width:
            break
        buffer.append(char)
        cells += char_cells

    return "".join(buffer)


def _truncate_text_from_end(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if _text_width(text) <= width:
        return text

    cells = 0
    buffer: List[str] = []

    for char in reversed(text):
        char_cells = _char_width(char)
        if cells + char_cells > width:
            break
        buffer.append(char)
        cells += char_cells

    return "".join(reversed(buffer))


def _pad_text(text: str, width: int, align: str = "left") -> str:
    visible = _truncate_text(text, width)
    padding = max(0, width - _text_width(visible))

    if align == "center":
        left = padding // 2
        right = padding - left
        return (" " * left) + visible + (" " * right)

    return visible + (" " * padding)


def _fit_text(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if _text_width(text) <= width:
        return text
    if width <= 1:
        return _truncate_text(text, width)
    return _truncate_text(text, width - 1) + "…"


class TerminalKaraokeDisplay:
    def __init__(self) -> None:
        self._opened = False

    def open(self) -> None:
        self._opened = True
        self._clear_screen()
        self._hide_cursor()

    def close(self) -> None:
        if not self._opened:
            return
        self._show_cursor()
        self._clear_screen()
        self._opened = False

    def render(
        self,
        song_title: str,
        artist_name: str,
        current_time: float,
        duration: float,
        lyric_text: str,
    ) -> None:
        columns, rows = self._get_terminal_size()

        info_width = min(max(36, self._content_width(song_title, artist_name, current_time, duration) + 4), max(20, columns - 4))
        lyric_width = max(20, columns - 4)

        info_box = self._build_info_box(
            title=song_title,
            artist=artist_name,
            current_time=current_time,
            duration=duration,
            box_width=info_width,
        )

        if lyric_text:
            lyric_line = self._prepare_lyric_line(lyric_text, lyric_width)
        else:
            lyric_line = self._center_or_crop("", lyric_width)

        total_block_height = len(info_box) + 2
        top_margin = max(1, (rows - total_block_height) // 2 - 1)

        lines: List[str] = []
        lines.extend([" " * columns] * top_margin)

        for line in info_box:
            lines.append(self._center_line(line, columns))

        lines.append(" " * columns)
        lines.append(self._center_line(lyric_line, columns))

        while len(lines) < rows:
            lines.append(" " * columns)

        self._move_cursor_home()
        sys.stdout.write(
            "\n".join(self._left_or_crop(line, columns) for line in lines[:rows])
        )
        sys.stdout.flush()

    def _build_info_box(
        self,
        title: str,
        artist: str,
        current_time: float,
        duration: float,
        box_width: int,
    ) -> List[str]:
        inner_width = max(1, box_width - 2)

        title_line = self._fit_text(title, inner_width - 2)
        artist_line = self._fit_text(artist, inner_width - 2)
        time_line = self._fit_text(
            f"{self._format_clock(current_time)} | {self._format_clock(duration)}",
            inner_width - 2,
        )

        return [
            "┌" + "─" * inner_width + "┐",
            "│" + self._center_or_crop(title_line, inner_width) + "│",
            "│" + self._center_or_crop(artist_line, inner_width) + "│",
            "│" + self._center_or_crop(time_line, inner_width) + "│",
            "└" + "─" * inner_width + "┘",
        ]

    def _content_width(
        self,
        title: str,
        artist: str,
        current_time: float,
        duration: float,
    ) -> int:
        time_line = f"{self._format_clock(current_time)} | {self._format_clock(duration)}"
        return max(_text_width(title), _text_width(artist), _text_width(time_line))

    def _get_terminal_size(self) -> Tuple[int, int]:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns, size.lines

    def _format_clock(self, seconds: float) -> str:
        seconds = max(0.0, seconds)
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _prepare_lyric_line(self, text: str, width: int) -> str:
        if width <= 0:
            return ""

        if _text_width(text) <= width:
            return _pad_text(text, width, "center")

        return _truncate_text_from_end(text, width)

    def _center_or_crop(self, text: str, width: int) -> str:
        return _pad_text(text, width, "center")

    def _center_line(self, text: str, width: int) -> str:
        return _pad_text(text, width, "center")

    def _left_or_crop(self, text: str, width: int) -> str:
        return _pad_text(text, width, "left")

    def _fit_text(self, text: str, width: int) -> str:
        return _fit_text(text, width)

    def _clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _move_cursor_home(self) -> None:
        sys.stdout.write("\033[H")
        sys.stdout.flush()

    def _hide_cursor(self) -> None:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def _show_cursor(self) -> None:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


class _RawTerminal:
    def __init__(self) -> None:
        self.fd: Optional[int] = None
        self.old_settings = None

    def __enter__(self) -> "_RawTerminal":
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None and self.old_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def read_key(self, timeout: float = 0.1) -> Optional[str]:
        if self.fd is None:
            return None

        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return None

        first = os.read(self.fd, 1)
        if not first:
            return None

        if first == b"\x1b":
            more, _, _ = select.select([self.fd], [], [], 0.01)
            if not more:
                return "escape"

            second = os.read(self.fd, 1)
            more, _, _ = select.select([self.fd], [], [], 0.01)
            third = os.read(self.fd, 1) if more else b""

            seq = first + second + third

            if seq == b"\x1b[A":
                return "up"
            if seq == b"\x1b[B":
                return "down"
            if seq == b"\x1b[C":
                return "right"
            if seq == b"\x1b[D":
                return "left"

            return "escape"

        if first in {b"\r", b"\n"}:
            return "enter"

        char = self._read_utf8_char(first)
        if char in {"q", "Q", "й", "Й"}:
            return "quit"

        return None

    def _read_utf8_char(self, first: bytes) -> Optional[str]:
        if self.fd is None or not first:
            return None

        expected_length = self._utf8_char_length(first[0])
        data = bytearray(first)

        while len(data) < expected_length:
            more, _, _ = select.select([self.fd], [], [], 0.01)
            if not more:
                break

            chunk = os.read(self.fd, 1)
            if not chunk:
                break

            data.extend(chunk)

        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _utf8_char_length(self, first_byte: int) -> int:
        if first_byte & 0b10000000 == 0:
            return 1
        if first_byte & 0b11100000 == 0b11000000:
            return 2
        if first_byte & 0b11110000 == 0b11100000:
            return 3
        if first_byte & 0b11111000 == 0b11110000:
            return 4
        return 1


class TerminalSongSelector(Generic[T]):
    def __init__(self, app_title: str = "Lyrona") -> None:
        self.app_title = app_title

    def select(self, labels: Sequence[str], values: Sequence[T]) -> Optional[T]:
        if not labels or not values or len(labels) != len(values):
            return None

        current_index = 0

        with _RawTerminal() as terminal:
            self._clear_screen()
            self._hide_cursor()
            try:
                while True:
                    self._render_menu(labels, values, current_index)
                    key = terminal.read_key(timeout=0.1)

                    if key == "up":
                        current_index = (current_index - 1) % len(labels)
                    elif key == "down":
                        current_index = (current_index + 1) % len(labels)
                    elif key == "enter":
                        return values[current_index]
                    elif key in {"quit", "escape"}:
                        return None
            finally:
                self._show_cursor()
                self._clear_screen()

    def _render_menu(
        self,
        labels: Sequence[str],
        values: Sequence[T],
        current_index: int,
    ) -> None:
        columns, rows = self._get_terminal_size()

        display_labels: List[str] = []
        for idx, label in enumerate(labels):
            display_labels.append(f"{idx + 1}. {label}")

        box_width = min(
            max(40, self._longest_label_width(display_labels) + 8),
            max(20, columns - 4),
        )
        box_height = len(display_labels) + 6

        top_margin = max(1, (rows - box_height) // 2 - 2)
        left_margin = max(0, (columns - box_width) // 2)

        title = self._fit_text(self.app_title, box_width - 4)
        artist_line = self._selection_artist_line(values, current_index, columns)
        help_line = "↑ ↓ move   Enter play   q / й quit"
        help_line = self._fit_text(help_line, columns)

        lines: List[str] = []
        lines.extend([" " * columns] * top_margin)
        lines.append(self._center_line(title, columns))
        lines.append(" " * columns)

        top = "┌" + "─" * (box_width - 2) + "┐"
        bottom = "└" + "─" * (box_width - 2) + "┘"

        lines.append(self._pad_left(top, left_margin, columns))

        for idx, item in enumerate(display_labels):
            prefix = "❯ " if idx == current_index else "  "
            content = self._fit_text(prefix + item, box_width - 4)
            row = "│ " + _pad_text(content, box_width - 4, "left") + " │"
            lines.append(self._pad_left(row, left_margin, columns))

        lines.append(self._pad_left(bottom, left_margin, columns))
        lines.append(" " * columns)
        if artist_line:
            lines.append(self._center_line(artist_line, columns))
        lines.append(self._center_line(help_line, columns))

        while len(lines) < rows:
            lines.append(" " * columns)

        sys.stdout.write("\033[H")
        sys.stdout.write("\n".join(_pad_text(line, columns, "left") for line in lines[:rows]))
        sys.stdout.flush()

    def _get_terminal_size(self) -> Tuple[int, int]:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns, size.lines

    def _longest_label_width(self, labels: Sequence[str]) -> int:
        longest = 0
        for label in labels:
            longest = max(longest, _text_width(label) + 2)
        return longest

    def _selection_artist_line(
        self,
        values: Sequence[T],
        current_index: int,
        width: int,
    ) -> str:
        if current_index < 0 or current_index >= len(values):
            return ""

        value = values[current_index]
        artist = getattr(value, "artist", "")
        if not isinstance(artist, str) or not artist.strip():
            return ""

        return self._fit_text(f"Artist: {artist.strip()}", width)

    def _fit_text(self, text: str, width: int) -> str:
        return _fit_text(text, width)

    def _center_line(self, text: str, width: int) -> str:
        return _pad_text(text, width, "center")

    def _pad_left(self, text: str, left_margin: int, total_width: int) -> str:
        if total_width <= 0:
            return ""
        padded = (" " * left_margin) + text
        return _pad_text(padded, total_width, "left")

    def _clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _hide_cursor(self) -> None:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def _show_cursor(self) -> None:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
