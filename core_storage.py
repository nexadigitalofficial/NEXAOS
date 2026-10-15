# core_storage.py - Thread-safe Atomic Persistence Shield (SYS-EVO P-002)
import os
import json
import tempfile
import threading

class AtomicJSONStore:
    _lock = threading.Lock()

    @classmethod
    def read(cls, file_path, default=None):
        with cls._lock:
            if not os.path.exists(file_path):
                return default if default is not None else {}
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return default if default is not None else {}

    @classmethod
    def write(cls, file_path, data):
        with cls._lock:
            abs_path = os.path.abspath(file_path)
            dir_name = os.path.dirname(abs_path)
            os.makedirs(dir_name, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                json.dump(data, tf, ensure_ascii=False, indent=2)
                temp_name = tf.name
            os.replace(temp_name, abs_path)
            return True

    @classmethod
    def write_text(cls, file_path, text):
        with cls._lock:
            abs_path = os.path.abspath(file_path)
            dir_name = os.path.dirname(abs_path)
            os.makedirs(dir_name, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                tf.write(text)
                temp_name = tf.name
            os.replace(temp_name, abs_path)
            return True
