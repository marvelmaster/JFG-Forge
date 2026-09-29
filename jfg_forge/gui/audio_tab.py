"""The "Audio" tab: play and export the game's music and sound effects."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from jfg_forge.core.audio_export import Mp3Unavailable, export_audio
from jfg_forge.core.audio_render import AudioEngine, Rendered
from jfg_forge.core.audio_rom import AudioRom, load_audio
from jfg_forge.core.rom_source import RomSource

try:  # QtMultimedia ships with PySide6 but may lack a working backend or device
    from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

    MULTIMEDIA_IMPORTED = True
except Exception:  # pragma: no cover - depends on the installation
    MULTIMEDIA_IMPORTED = False


def format_time(seconds: float) -> str:
    seconds = max(int(round(seconds)), 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass(frozen=True)
class AudioEntry:
    index: int
    label: str
    tooltip: str = ""
    playable: bool = True
    looping: bool = False


def filter_entries(
    entries: list[AudioEntry],
    *,
    text: str = "",
    only_looping: bool = False,
    hide_unplayable: bool = True,
) -> list[AudioEntry]:
    """Apply the search text and checkboxes of an audio page (Qt-free, testable)."""
    needle = text.strip().lower()
    result = []
    for entry in entries:
        if hide_unplayable and not entry.playable:
            continue
        if only_looping and not entry.looping:
            continue
        if needle and needle not in entry.label.lower() and needle != str(entry.index):
            continue
        result.append(entry)
    return result


class Player(QObject):
    """Plays one rendered clip at a time through the default audio output."""

    started = Signal()
    finished = Signal()
    position = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sink = None
        self._buffer: QBuffer | None = None
        self._bytes_per_second = 1
        self._volume = 0.8
        self._playing = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

    @property
    def available(self) -> bool:
        return MULTIMEDIA_IMPORTED and not QMediaDevices.defaultAudioOutput().isNull()

    @property
    def playing(self) -> bool:
        return self._playing

    def set_volume(self, volume: float) -> None:
        self._volume = min(max(volume, 0.0), 1.0)
        if self._sink is not None:
            self._sink.setVolume(self._volume)

    def play(self, audio: Rendered) -> None:
        self.stop()
        if not self.available:
            raise RuntimeError("No audio output device is available.")
        device = QMediaDevices.defaultAudioOutput()
        samples = audio.samples
        rate = audio.sample_rate
        channels = audio.channels
        fmt = QAudioFormat()
        fmt.setSampleRate(rate)
        fmt.setChannelCount(channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            # Fall back to the device's preferred rate; resample by linear interpolation.
            preferred = device.preferredFormat()
            target = preferred.sampleRate() or 48000
            positions = np.arange(int(len(samples) * target / rate)) * (rate / target)
            index = np.arange(len(samples))
            if samples.ndim == 1:
                samples = np.interp(positions, index, samples).astype(np.float32)
            else:
                samples = np.column_stack(
                    [np.interp(positions, index, samples[:, c]) for c in range(channels)]
                ).astype(np.float32)
            rate = target
            fmt.setSampleRate(rate)
        pcm = np.clip(np.round(samples * 32767.0), -32768, 32767).astype("<i2")
        self._bytes_per_second = rate * channels * 2
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(pcm.tobytes()))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._sink = QAudioSink(device, fmt, self)
        self._sink.setVolume(self._volume)
        self._sink.start(self._buffer)
        self._playing = True
        self._timer.start()
        self.started.emit()

    def stop(self) -> None:
        was_playing = self._playing
        self._timer.stop()
        self._playing = False
        if self._sink is not None:
            self._sink.stop()
            self._sink.deleteLater()
            self._sink = None
        if self._buffer is not None:
            self._buffer.close()
            self._buffer.deleteLater()
            self._buffer = None
        if was_playing:
            self.finished.emit()

    def _tick(self) -> None:
        if self._sink is None or self._buffer is None:
            return
        elapsed = self._sink.processedUSecs() / 1_000_000
        self.position.emit(elapsed)
        if self._buffer.atEnd() and elapsed * self._bytes_per_second >= self._buffer.size() - self._bytes_per_second * 0.05:
            self.stop()


_RENDER_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jfg-audio-render")


class AudioPage(QWidget):
    """One list of clips with playback and export controls."""

    def __init__(
        self,
        title: str,
        entries: list[AudioEntry],
        render: Callable[[int], Rendered | None],
        describe: Callable[[int, Rendered | None], list[tuple[str, str]]],
        default_name: Callable[[int], str],
        player: Player,
        *,
        background: bool,
        autoplay: bool,
        extra_filter: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self._entries = entries
        self._render = render
        self._describe = describe
        self._default_name = default_name
        self._player = player
        self._background = background
        self._cache: dict[int, Rendered] = {}
        self._current: int | None = None
        self._pending: int | None = None
        self._job: tuple[int, Future] | None = None
        self._poll = QTimer(self)
        self._poll.setInterval(50)
        self._poll.timeout.connect(self._poll_job)
        self._duration = 0.0

        layout = QHBoxLayout(self)
        left = QFrame()
        left.setMinimumWidth(260)
        left_layout = QVBoxLayout(left)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by number")
        self.search_edit.setClearButtonEnabled(True)
        left_layout.addWidget(self.search_edit)
        self.filter_check = QCheckBox(extra_filter) if extra_filter else None
        if self.filter_check is not None:
            left_layout.addWidget(self.filter_check)
        self.count_label = QLabel("")
        left_layout.addWidget(self.count_label)
        self.list_widget = QListWidget()
        left_layout.addWidget(self.list_widget, stretch=1)
        layout.addWidget(left, stretch=0)

        right = QFrame()
        right_layout = QVBoxLayout(right)
        self.heading = QLabel("Select an entry from the list.")
        self.heading.setStyleSheet("font-weight: bold; font-size: 16px;")
        right_layout.addWidget(self.heading)
        self.info_form = QFormLayout()
        self.info_values: dict[str, QLabel] = {}
        right_layout.addLayout(self.info_form)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        right_layout.addLayout(controls)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.setEnabled(False)
        right_layout.addWidget(self.progress)
        self.time_label = QLabel("0:00 / 0:00")
        right_layout.addWidget(self.time_label)
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        volume_row.addWidget(self.volume_slider)
        right_layout.addLayout(volume_row)
        self.autoplay_check = QCheckBox("Play when selected")
        self.autoplay_check.setChecked(autoplay)
        right_layout.addWidget(self.autoplay_check)

        export_row = QHBoxLayout()
        self.wav_button = QPushButton("Export WAV...")
        self.mp3_button = QPushButton("Export MP3...")
        export_row.addWidget(self.wav_button)
        export_row.addWidget(self.mp3_button)
        right_layout.addLayout(export_row)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)
        right_layout.addStretch(1)
        layout.addWidget(right, stretch=1)

        self.search_edit.textChanged.connect(self._refresh_list)
        if self.filter_check is not None:
            self.filter_check.toggled.connect(self._refresh_list)
        self.list_widget.currentItemChanged.connect(self._select_item)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.play_current())
        self.play_button.clicked.connect(self.play_current)
        self.stop_button.clicked.connect(self._player.stop)
        self.volume_slider.valueChanged.connect(lambda value: self._player.set_volume(value / 100.0))
        self.wav_button.clicked.connect(lambda: self.export_current("wav"))
        self.mp3_button.clicked.connect(lambda: self.export_current("mp3"))
        self._player.position.connect(self._position)
        self._player.finished.connect(self._playback_finished)
        self._refresh_list()

    # ------------------------------------------------------------------ list
    def _refresh_list(self, *_args: object) -> None:
        rows = filter_entries(
            self._entries,
            text=self.search_edit.text(),
            only_looping=bool(self.filter_check and self.filter_check.isChecked() and "loop" in self.filter_check.text().lower()),
            hide_unplayable=True,
        )
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        keep = self._current
        selected = -1
        for row, entry in enumerate(rows):
            item = QListWidgetItem(entry.label)
            item.setData(Qt.ItemDataRole.UserRole, entry.index)
            item.setToolTip(entry.tooltip)
            self.list_widget.addItem(item)
            if entry.index == keep:
                selected = row
        if selected >= 0:
            self.list_widget.setCurrentRow(selected)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(rows)} of {len(self._entries)} entries")

    def _entry(self, index: int) -> AudioEntry:
        return next(entry for entry in self._entries if entry.index == index)

    def _select_item(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if item is None:
            return
        self.select(int(item.data(Qt.ItemDataRole.UserRole)))

    def select(self, index: int) -> None:
        self._player.stop()
        self._current = index
        entry = self._entry(index)
        self.heading.setText(entry.label.strip())
        self._show_details(index, self._cache.get(index))
        self._reset_progress(self._cache[index].seconds if index in self._cache else 0.0)
        if self.autoplay_check.isChecked():
            self.play_current()

    def _show_details(self, index: int, rendered: Rendered | None) -> None:
        while self.info_form.rowCount():
            self.info_form.removeRow(0)
        self.info_values.clear()
        for name, value in self._describe(index, rendered):
            label = QLabel(value)
            label.setWordWrap(True)
            self.info_form.addRow(name, label)
            self.info_values[name] = label

    # ------------------------------------------------------------------ playback
    def rendered_for(self, index: int) -> Rendered | None:
        """Render (and cache) the clip synchronously."""
        if index not in self._cache:
            audio = self._render(index)
            if audio is None:
                return None
            self._cache[index] = audio
            while len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
        return self._cache[index]

    def play_current(self) -> None:
        if self._current is None:
            return
        index = self._current
        if index in self._cache or not self._background:
            self._start(index)
            return
        self._pending = index
        self.status_label.setText("Rendering...")
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        self._job = (index, _RENDER_POOL.submit(self._render, index))
        self._poll.start()

    def _poll_job(self) -> None:
        if self._job is None:
            self._poll.stop()
            return
        index, future = self._job
        if not future.done():
            return
        self._poll.stop()
        self._job = None
        try:
            self._render_done(index, future.result())
        except Exception as error:
            self._render_failed(index, str(error))

    def _render_done(self, index: int, audio: object) -> None:
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        if audio is not None:
            self._cache[index] = audio  # type: ignore[assignment]
            while len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
        if self._pending == index and self._current == index:
            self._pending = None
            self._start(index)
        elif self._current == index:
            self._show_details(index, self._cache.get(index))

    def _render_failed(self, index: int, message: str) -> None:
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.status_label.setText(f"Could not render this entry: {message}")

    def _start(self, index: int) -> None:
        try:
            audio = self.rendered_for(index)
        except Exception as error:
            self.status_label.setText(f"Could not render this entry: {error}")
            return
        if audio is None:
            self.status_label.setText("This entry has no sample to play.")
            return
        self._show_details(index, audio)
        self._reset_progress(audio.seconds)
        if not self._player.available:
            self.status_label.setText("No audio output device found; exporting still works.")
            return
        try:
            self._player.play(audio)
        except Exception as error:
            self.status_label.setText(f"Playback failed: {error}")
            return
        self.status_label.setText("Playing.")
        self.play_button.setText("Restart")

    def _reset_progress(self, seconds: float) -> None:
        self._duration = seconds
        self.progress.setValue(0)
        self.time_label.setText(f"0:00 / {format_time(seconds)}")

    def _position(self, seconds: float) -> None:
        if self._duration > 0:
            self.progress.setValue(min(int(seconds / self._duration * 1000), 1000))
        self.time_label.setText(f"{format_time(seconds)} / {format_time(self._duration)}")

    def _playback_finished(self) -> None:
        self.play_button.setText("Play")
        if self.status_label.text() == "Playing.":
            self.status_label.setText("")
        self.progress.setValue(0)

    # ------------------------------------------------------------------ export
    def export_current(self, kind: str) -> None:
        if self._current is None:
            QMessageBox.information(self, "JFG Forge", "Select an entry to export first.")
            return
        index = self._current
        stem = self._default_name(index)
        filters = "WAV audio (*.wav)" if kind == "wav" else "MP3 audio (*.mp3)"
        destination, _selected = QFileDialog.getSaveFileName(
            self, f"Export {kind.upper()}", f"{stem}.{kind}", filters
        )
        if not destination:
            return
        path = Path(destination)
        if path.suffix.lower() != f".{kind}":
            path = path.with_suffix(f".{kind}")
        self.export_to(index, path)

    def export_to(self, index: int, path: Path) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            audio = self.rendered_for(index)
            if audio is None:
                raise RuntimeError("this entry has no sample")
            export_audio(path, audio)
        except Mp3Unavailable as error:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "MP3 export unavailable", str(error))
            return False
        except Exception as error:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "JFG Forge export error", str(error))
            self.status_label.setText(f"Export failed: {error}")
            return False
        QApplication.restoreOverrideCursor()
        self.status_label.setText(f"Exported {path.name} ({format_time(audio.seconds)}, {audio.sample_rate} Hz).")
        return True


class AudioTab(QWidget):
    """Music and Sounds segments over one shared player."""

    def __init__(self, source: RomSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self.audio: AudioRom | None = None
        self.engine: AudioEngine | None = None
        self.player = Player(self)
        self.music_page: AudioPage | None = None
        self.sounds_page: AudioPage | None = None
        self.segments = QTabWidget()
        self.segments.setDocumentMode(True)
        self._placeholder = QLabel("Loading audio ...")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._placeholder)
        layout.addWidget(self.segments)
        self.segments.hide()
        self.segments.currentChanged.connect(lambda _index: self.player.stop())
        self.loaded = False

    def ensure_loaded(self) -> None:
        """Read the audio data the first time the tab is opened."""
        if self.loaded:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.audio = load_audio(self._source)
            self.engine = AudioEngine(self.audio)
            self._build_pages()
        except Exception as error:
            QApplication.restoreOverrideCursor()
            self._placeholder.setText(f"The audio data could not be read: {error}")
            return
        QApplication.restoreOverrideCursor()
        self.loaded = True
        self._placeholder.hide()
        self.segments.show()

    def _build_pages(self) -> None:
        audio, engine = self.audio, self.engine
        assert audio is not None and engine is not None

        song_entries = []
        for song in audio.songs:
            decoded = engine.sequence(song)
            notes = sum(1 for e in decoded.events if e.kind == "note")
            silent = notes == 0
            song_entries.append(
                AudioEntry(
                    song.song_id,
                    f"Song {song.song_id:02d}   {format_time(decoded.seconds())}   {notes} notes",
                    "Empty placeholder without any notes" if silent else "",
                    playable=not silent,
                )
            )

        def describe_song(index: int, rendered: Rendered | None) -> list[tuple[str, str]]:
            song = audio.songs[index]
            decoded = engine.sequence(song)
            notes = [e for e in decoded.events if e.kind == "note"]
            tempo = next((e.a for e in decoded.events if e.kind == "tempo"), 500000)
            rows = [
                ("Song", f"{index} of {len(audio.songs) - 1}"),
                ("Notes", str(len(notes))),
                ("Tempo", f"{60_000_000 / tempo:.0f} beats per minute"),
                ("Instruments", str(len({e.a for e in decoded.events if e.kind == 'program'}))),
                ("Plays", "once through; an endless loop stops after one pass" if decoded.looped else "once through"),
            ]
            if rendered is not None:
                rows.append(("Rendered", f"{format_time(rendered.seconds)}, stereo, {rendered.sample_rate} Hz"))
            return rows

        self.music_page = AudioPage(
            "Music",
            song_entries,
            engine.render_song,
            describe_song,
            lambda index: f"Song_{index:02d}",
            self.player,
            background=True,
            autoplay=False,
        )

        effect_entries = []
        for effect in audio.effects:
            sound = engine.effect_sound(effect)
            loop = sound.wave.loop if sound is not None else None
            looping = bool(loop and loop.end > loop.start and loop.count != 0)
            effect_entries.append(
                AudioEntry(
                    effect.sound_id,
                    f"Sound {effect.sound_id:03d}" + ("   (loops)" if looping else ""),
                    f"Sample {effect.bite}, pitch {effect.pitch}, volume {effect.volume}",
                    playable=sound is not None,
                    looping=looping,
                )
            )

        def describe_effect(index: int, rendered: Rendered | None) -> list[tuple[str, str]]:
            effect = audio.effects[index]
            sound = engine.effect_sound(effect)
            rows = [
                ("Sound", f"{index} of {len(audio.effects) - 1}"),
                ("Sample", str(effect.bite)),
                ("Pitch", f"{effect.pitch}%"),
                ("Volume", str(effect.volume)),
                ("Hearing range", str(effect.range)),
            ]
            loop = sound.wave.loop if sound is not None else None
            if loop and loop.end > loop.start and loop.count != 0:
                rows.append(("Looping", "yes; repeated for 3 seconds"))
            if rendered is not None:
                rows.append(("Length", f"{rendered.seconds:.2f} s, mono, {rendered.sample_rate} Hz"))
            return rows

        self.sounds_page = AudioPage(
            "Sounds",
            effect_entries,
            lambda index: engine.render_effect(index),
            describe_effect,
            lambda index: f"Sound_{index:03d}",
            self.player,
            background=False,
            autoplay=True,
            extra_filter="Only looping sounds",
        )
        self.segments.addTab(self.music_page, "Music")
        self.segments.addTab(self.sounds_page, "Sounds")

    def stop(self) -> None:
        self.player.stop()


__all__ = ["AudioEntry", "AudioPage", "AudioTab", "Player", "filter_entries", "format_time"]
