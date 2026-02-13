import openwakeword
from openwakeword.model import Model
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import threading
import logging
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import VoiceConfig

logger = logging.getLogger(__name__)


def list_wakewords() -> List[str]:
    """Lists all available pretrained wakewords."""
    paths = openwakeword.get_pretrained_model_paths() or []
    # Extract filename without extension and remove common version suffixes
    # Paths look like: /path/to/models/hey_jarvis_v0.1.tflite
    names = set()
    for p in paths:
        filename = Path(p).stem
        # Remove common versioning patterns like _v0.1, _v1.0
        import re

        base_name = re.sub(r"_v\d+(\.\d+)*$", "", filename)
        names.add(base_name)
    return sorted(list(names))


class WakeWordEngine(Reconfigurable):
    """
    A wrapper around openWakeWord for local keyword detection.
    Supports multiple concurrent models (e.g. start word and stop word).
    """

    config_key = "voice"

    def __init__(
        self,
        start_word: Optional[str] = None,
        stop_word: Optional[str] = None,
        sensitivity: float = 0.5,
        stop_sensitivity: float = 0.5,
    ):
        self._lock = threading.RLock()
        self.start_word = start_word
        self.stop_word = stop_word
        self.threshold = 1.0 - sensitivity
        self.stop_threshold = 1.0 - stop_sensitivity
        self.start_model: Optional[Model] = None
        self.stop_model: Optional[Model] = None
        self._loaded_start_name: Optional[str] = None
        self._loaded_stop_name: Optional[str] = None
        self._load_models()

    def _load_models(self):
        """Loads the models specified by start_word and stop_word separately."""
        with self._lock:
            self.start_model = None
            self.stop_model = None
            self._loaded_start_name = None
            self._loaded_stop_name = None

            pretrained_paths = openwakeword.get_pretrained_model_paths() or []

            def get_target_path(name):
                if not name:
                    return None
                m_name = name.lower()
                # Check if it's a pretrained model name
                matches = [
                    p for p in pretrained_paths if m_name in Path(p).name.lower()
                ]
                if matches:
                    return m_name
                elif Path(name).exists():
                    return name
                return None

            start_path = get_target_path(self.start_word)
            if start_path:
                logger.info(f"Loading Start WakeWord model: {start_path}")
                try:
                    self.start_model = Model(
                        wakeword_models=[start_path],
                        inference_framework="onnx",
                        device="cpu",
                    )
                    self._loaded_start_name = self.start_word
                except Exception as e:
                    logger.error(
                        f"Failed to load start wakeword model '{start_path}': {e}"
                    )

            stop_path = get_target_path(self.stop_word)
            if stop_path:
                logger.info(f"Loading Stop WakeWord model: {stop_path}")
                try:
                    self.stop_model = Model(
                        wakeword_models=[stop_path],
                        inference_framework="onnx",
                        device="cpu",
                    )
                    self._loaded_stop_name = self.stop_word
                except Exception as e:
                    logger.error(
                        f"Failed to load stop wakeword model '{stop_path}': {e}"
                    )

    def reconfigure(self, config: BaseModel) -> None:
        """Update wakeword models and sensitivity based on config."""
        if isinstance(config, VoiceConfig):
            with self._lock:
                changed = False
                if (
                    config.wakeword != self.start_word
                    or config.stop_wakeword != self.stop_word
                ):
                    logger.info(
                        f"Reconfiguring WakeWord models: Start={config.wakeword}, Stop={config.stop_wakeword}"
                    )
                    self.start_word = config.wakeword
                    self.stop_word = config.stop_wakeword
                    changed = True

                new_threshold = 1.0 - config.wakeword_sensitivity
                if new_threshold != self.threshold:
                    logger.info(f"WakeWord threshold updated to {new_threshold:.2f}")
                    self.threshold = new_threshold
                    changed = True

                new_stop_threshold = 1.0 - config.stop_wakeword_sensitivity
                if new_stop_threshold != self.stop_threshold:
                    logger.info(
                        f"Stop word threshold updated to {new_stop_threshold:.2f}"
                    )
                    self.stop_threshold = new_stop_threshold
                    changed = True

                if changed:
                    self._load_models()

    @property
    def active_start_word(self) -> Optional[str]:
        with self._lock:
            return self._loaded_start_name

    @property
    def active_stop_word(self) -> Optional[str]:
        with self._lock:
            return self._loaded_stop_name

    @property
    def active_wakeword(self) -> Optional[str]:
        return self.active_start_word

    def process_chunk(
        self, chunk: np.ndarray, word: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Process an audio chunk and return detection probabilities for the specified word
        or the start word if None.
        """
        if chunk.dtype != np.int16:
            chunk_int16 = (chunk * 32767).astype(np.int16)
        else:
            chunk_int16 = chunk

        with self._lock:
            # Select model based on requested word
            target_model = None
            target_name = None

            if (
                word
                and self.stop_word
                and (word == self.stop_word or word in self.stop_word)
            ):
                target_model = self.stop_model
                target_name = self.stop_word
            else:
                target_model = self.start_model
                target_name = self.start_word

            if not target_model:
                return {}

            prediction = target_model.predict(chunk_int16)

        if isinstance(prediction, tuple):
            prediction = prediction[0]

        # Normalize keys
        normalized = {}
        with self._lock:
            for k, v in prediction.items():
                if target_name and (target_name in k or k == target_name):
                    normalized[target_name] = max(normalized.get(target_name, 0.0), v)
                else:
                    normalized[k] = v
        return normalized

    def detect(
        self,
        chunk: np.ndarray,
        word: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Returns True if the specified word (or the start word if None) is detected.
        """
        probabilities = self.process_chunk(chunk, word=word)
        with self._lock:
            target_word = word or self.start_word
            if not target_word:
                return False

            if threshold is not None:
                target_threshold = threshold
            elif target_word == self.stop_word:
                target_threshold = self.stop_threshold
            else:
                target_threshold = self.threshold

            prob = probabilities.get(target_word, 0.0)
            if prob > 0.01:
                logger.info(
                    f"   [WW] '{target_word}' prob: {prob:.4f} (threshold: {target_threshold:.2f})"
                )

            return prob >= target_threshold

    def reset(self):
        """Resets the internal state of the wake-word models."""
        with self._lock:
            if self.start_model:
                self.start_model.reset()
            if self.stop_model:
                self.stop_model.reset()
