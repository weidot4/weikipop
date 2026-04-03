import requests
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AnkiClient:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')

    # Actions that transfer large data need a longer timeout
    _LONG_TIMEOUT_ACTIONS = {"storeMediaFile", "addNote"}

    def _invoke(self, action: str, **params) -> Any:
        payload = {
            "action": action,
            "version": 6,
            "params": params
        }
        timeout = 30.0 if action in self._LONG_TIMEOUT_ACTIONS else 2.0
        try:
            response = requests.post(self.api_url, json=payload, timeout=timeout) 
            response.raise_for_status()
            result = response.json()
            if len(result) != 2:
                raise ValueError("Response has an unexpected number of fields.")
            if "error" not in result:
                raise ValueError("Response is missing required error field.")
            if "result" not in result:
                raise ValueError("Response is missing required result field.")
            if result["error"]:
                raise Exception(result["error"])
            return result["result"]
        except Exception as e:
            logger.error(f"AnkiConnect error ({action}): {e}")
            raise e

    def ping(self, timeout: float = 0.8) -> bool:
        """Checks if AnkiConnect is reachable. Short timeout so failure is fast."""
        try:
            payload = {"action": "version", "version": 6, "params": {}}
            r = requests.post(self.api_url, json=payload, timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    def get_deck_names(self) -> List[str]:
        """Returns a list of all deck names."""
        try:
            return self._invoke("deckNames")
        except:
            return []

    def get_model_names(self) -> List[str]:
        """Returns a list of all note type (model) names."""
        try:
            return self._invoke("modelNames")
        except:
            return []

    def get_model_field_names(self, model_name: str) -> List[str]:
        """Returns a list of field names for the given model."""
        try:
            return self._invoke("modelFieldNames", modelName=model_name)
        except:
            return []

    def add_note(self, note_data: Dict[str, Any]) -> int:
        """
        Adds a note to Anki.
        note_data structure should match 'note' param in 'addNote' action.
        Returns the ID of the created note.
        """
        return self._invoke("addNote", note=note_data)

    def store_media_file(self, filename: str, data_base64: str) -> str:
        """Stores a media file in Anki."""
        return self._invoke("storeMediaFile", filename=filename, data=data_base64)

    def find_notes(self, query: str) -> List[int]:
        """Finds notes matching the query."""
        try:
            return self._invoke("findNotes", query=query)
        except:
            return []

