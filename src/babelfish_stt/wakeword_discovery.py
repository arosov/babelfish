"""Wake word model discovery for custom models in openwakeword_models/ directory."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

CUSTOM_MODEL_SUFFIX = "*"
VALID_EXTENSIONS = {".onnx", ".tflite"}

# Wake words to exclude from the list (e.g., command-specific words not supported by the application)
EXCLUDED_WAKEWORDS = {"timer", "weather"}


def scan_custom_models(app_data_dir: str, model_type: str) -> Dict[str, str]:
    """
    Scan the openwakeword_models directory for custom wake word models.

    Args:
        app_data_dir: The application data directory (e.g., ~/.config/vogonpoet)
        model_type: Either "start" or "stop" to specify which subdirectory to scan

    Returns:
        Dict mapping model names (with * suffix) to full file paths
    """
    models_dir = Path(app_data_dir) / "openwakeword_models" / model_type
    custom_models: Dict[str, str] = {}

    if not models_dir.exists():
        logger.debug(f"Custom models directory does not exist: {models_dir}")
        return custom_models

    if not models_dir.is_dir():
        logger.warning(f"Custom models path is not a directory: {models_dir}")
        return custom_models

    # Scan recursively: openwakeword_models/{model_type}/{lang}/{modelname}/
    for model_file in models_dir.rglob("*"):
        if not model_file.is_file():
            continue

        if model_file.suffix.lower() not in VALID_EXTENSIONS:
            continue

        # Validate the model file
        if not validate_model_file(str(model_file)):
            continue

        # Extract model name from parent directory or filename
        model_name = _extract_model_name(model_file, models_dir)
        if model_name:
            display_name = f"{model_name}{CUSTOM_MODEL_SUFFIX}"
            custom_models[display_name] = str(model_file)
            logger.info(f"Found custom model: {display_name} -> {model_file}")

    return custom_models


def _extract_model_name(model_file: Path, base_dir: Path) -> Optional[str]:
    """
    Extract a display name for the model from its path.

    Uses the directory name closest to the file, falling back to filename stem.
    """
    try:
        # Get relative path from base_dir
        rel_path = model_file.relative_to(base_dir)

        # If file is in a subdirectory, use the immediate parent directory name
        if len(rel_path.parts) > 1:
            # Path is like: lang/modelname/model.onnx
            # Use "modelname" as the model name
            model_name = rel_path.parts[-2]
        else:
            # File is directly in base_dir, use filename without extension
            model_name = model_file.stem

        # Sanitize the name (remove invalid characters)
        model_name = _sanitize_model_name(model_name)

        return model_name if model_name else None
    except Exception as e:
        logger.warning(f"Failed to extract model name from {model_file}: {e}")
        return None


def _sanitize_model_name(name: str) -> str:
    """Sanitize a model name for display purposes."""
    # Remove the * suffix if present (shouldn't happen but safety check)
    name = name.rstrip("*")

    # Replace spaces and special characters with underscores
    sanitized = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    return sanitized


def validate_model_file(path: str) -> bool:
    """
    Validate that a model file exists and is readable.

    Args:
        path: Full path to the model file

    Returns:
        True if valid, False otherwise (errors are logged)
    """
    try:
        file_path = Path(path)

        if not file_path.exists():
            logger.warning(f"Model file does not exist: {path}")
            return False

        if not file_path.is_file():
            logger.warning(f"Model path is not a file: {path}")
            return False

        # Check if file is readable
        if not file_path.stat().st_size > 0:
            logger.warning(f"Model file is empty: {path}")
            return False

        # Try to read first few bytes to verify it's readable
        try:
            with open(file_path, "rb") as f:
                f.read(1)
        except Exception as e:
            logger.error(f"Model file is not readable: {path} - {e}")
            return False

        return True

    except Exception as e:
        logger.error(f"Failed to validate model file {path}: {e}")
        return False


def get_model_path(display_name: str, custom_models: Dict[str, str]) -> Optional[str]:
    """
    Get the full path for a model by its display name.

    Args:
        display_name: Model name (with or without * suffix)
        custom_models: Dictionary of custom models from scan_custom_models()

    Returns:
        Full path if it's a custom model, None otherwise
    """
    # Ensure the name has the * suffix for lookup
    if not display_name.endswith(CUSTOM_MODEL_SUFFIX):
        display_name = f"{display_name}{CUSTOM_MODEL_SUFFIX}"

    return custom_models.get(display_name)


def is_custom_model(display_name: str) -> bool:
    """Check if a display name indicates a custom model."""
    return display_name.endswith(CUSTOM_MODEL_SUFFIX)


def strip_custom_suffix(display_name: str) -> str:
    """Remove the custom model suffix from a display name."""
    return display_name.rstrip(CUSTOM_MODEL_SUFFIX)
