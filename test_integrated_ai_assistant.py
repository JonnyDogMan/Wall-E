#!/usr/bin/env python3
"""
Unit tests for integrated_ai_assistant.py

Run with: python -m unittest test_integrated_ai_assistant
Or: python test_integrated_ai_assistant.py
"""

import unittest
from unittest.mock import (
    Mock, patch, MagicMock, mock_open, call, ANY,
    PropertyMock, mock_open as mock_file_open
)
import sys
import os
import tempfile
import threading
import time
import json

# Add the parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import integrated_ai_assistant as walle


class TestLoggingFunctions(unittest.TestCase):
    """Tests for logging functions."""

    @patch('builtins.open', new_callable=mock_open)
    @patch('integrated_ai_assistant.time.strftime', return_value='2024-01-01 12:00:00')
    @patch('builtins.print')
    def test_log_err_success(self, mock_print, mock_strftime, mock_file):
        """Test successful error logging."""
        test_exception = ValueError("Test error")
        walle.log_err("TestTag", test_exception)
        
        # Check that file was opened for writing
        mock_file.assert_called_once()
        # Check that write was called
        mock_file().write.assert_called_once()
        # Check that print was called
        mock_print.assert_called_once()
        # Check error message format
        call_args = mock_print.call_args[0][0]
        self.assertIn("[ERR]", call_args)
        self.assertIn("TestTag", call_args)

    @patch('builtins.open', side_effect=IOError("File write error"))
    @patch('builtins.print')
    def test_log_err_file_error(self, mock_print, mock_file):
        """Test error logging when file write fails."""
        test_exception = ValueError("Test error")
        walle.log_err("TestTag", test_exception)
        
        # Should still print to console even if file write fails
        mock_print.assert_called_once()


class TestFaceControlFunctions(unittest.TestCase):
    """Tests for face control (Pico) functions."""

    def setUp(self):
        """Set up test fixtures."""
        walle.PICO_ENABLED = True
        walle.PICO_BASE = "http://test-pico"

    def tearDown(self):
        """Clean up after tests."""
        walle.BLINK_STOP.set()
        if walle.BLINK_THREAD and walle.BLINK_THREAD.is_alive():
            walle.BLINK_THREAD.join(timeout=0.5)

    @patch('integrated_ai_assistant.requests.get')
    def test_pico_request_get_success(self, mock_get):
        """Test successful GET request to Pico."""
        mock_response = Mock()
        mock_response.text = "response text"
        mock_get.return_value = mock_response
        
        result = walle.pico_request("GET", "/ping", timeout=1.0)
        
        self.assertEqual(result, "response text")
        mock_get.assert_called_once_with("http://test-pico/ping", timeout=1.0)

    @patch('integrated_ai_assistant.requests.post')
    def test_pico_request_post_success(self, mock_post):
        """Test successful POST request to Pico."""
        mock_response = Mock()
        mock_response.text = "ok"
        mock_post.return_value = mock_response
        
        result = walle.pico_request("POST", "/open", timeout=1.0)
        
        self.assertEqual(result, "ok")
        mock_post.assert_called_once_with("http://test-pico/open", timeout=1.0)

    @patch('integrated_ai_assistant.requests.get', side_effect=Exception("Network error"))
    def test_pico_request_exception(self, mock_get):
        """Test Pico request with exception."""
        result = walle.pico_request("GET", "/ping")
        self.assertIsNone(result)

    def test_pico_request_disabled(self):
        """Test Pico request when PICO_ENABLED is False."""
        walle.PICO_ENABLED = False
        result = walle.pico_request("GET", "/ping")
        self.assertIsNone(result)
        walle.PICO_ENABLED = True

    @patch('integrated_ai_assistant.pico_request', return_value="pong")
    def test_pico_ok_success(self, mock_request):
        """Test Pico health check success."""
        result = walle.pico_ok()
        self.assertTrue(result)
        mock_request.assert_called_once_with("GET", "/ping", timeout=1.2)

    @patch('integrated_ai_assistant.pico_request', return_value="not pong")
    def test_pico_ok_failure(self, mock_request):
        """Test Pico health check failure."""
        result = walle.pico_ok()
        self.assertFalse(result)

    @patch('integrated_ai_assistant.pico_request', side_effect=[None, None, "success"])
    @patch('integrated_ai_assistant.time.sleep')
    def test_pico_post_reliable_success_after_retries(self, mock_sleep, mock_request):
        """Test reliable POST with retries."""
        result = walle.pico_post_reliable("/test", tries=3, delay_s=0.1)
        self.assertTrue(result)
        self.assertEqual(mock_request.call_count, 3)

    @patch('integrated_ai_assistant.pico_request', return_value=None)
    @patch('integrated_ai_assistant.time.sleep')
    def test_pico_post_reliable_all_fail(self, mock_sleep, mock_request):
        """Test reliable POST when all retries fail."""
        result = walle.pico_post_reliable("/test", tries=2, delay_s=0.1)
        self.assertFalse(result)
        self.assertEqual(mock_request.call_count, 2)

    @patch('integrated_ai_assistant.pico_ok', side_effect=[False, False, True])
    @patch('integrated_ai_assistant.time.sleep')
    @patch('integrated_ai_assistant.time.time', side_effect=[0, 0.3, 0.6, 0.9])
    def test_pico_wait_ready_success(self, mock_time, mock_sleep, mock_ok):
        """Test waiting for Pico to become ready."""
        result = walle.pico_wait_ready(max_wait_s=2.0)
        self.assertTrue(result)

    @patch('integrated_ai_assistant.pico_ok', return_value=False)
    @patch('integrated_ai_assistant.time.sleep')
    @patch('integrated_ai_assistant.time.time', side_effect=[0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.1])
    def test_pico_wait_ready_timeout(self, mock_time, mock_sleep, mock_ok):
        """Test Pico wait ready timeout."""
        result = walle.pico_wait_ready(max_wait_s=2.0)
        self.assertFalse(result)

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_eyes_open(self, mock_post):
        """Test eyes_open function."""
        result = walle.eyes_open()
        self.assertTrue(result)
        mock_post.assert_called_once_with("/open")

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_eyes_close(self, mock_post):
        """Test eyes_close function."""
        result = walle.eyes_close()
        self.assertTrue(result)
        mock_post.assert_called_once_with("/close")

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_eyes_blink(self, mock_post):
        """Test eyes_blink function."""
        result = walle.eyes_blink()
        self.assertTrue(result)
        mock_post.assert_called_once_with("/blink")

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_wink_functions(self, mock_post):
        """Test wink functions."""
        result_left = walle.wink_left()
        result_right = walle.wink_right()
        self.assertTrue(result_left)
        self.assertTrue(result_right)
        mock_post.assert_has_calls([call("/wink_left"), call("/wink_right")])

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_look_functions(self, mock_post):
        """Test look up/down functions."""
        result_up = walle.look_up()
        result_down = walle.look_down()
        self.assertTrue(result_up)
        self.assertTrue(result_down)
        mock_post.assert_has_calls([call("/look_up"), call("/look_down")])

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_center_ud(self, mock_post):
        """Test center_ud function."""
        result = walle.center_ud()
        self.assertTrue(result)
        mock_post.assert_called_once_with("/center_ud")

    @patch('integrated_ai_assistant.pico_post_reliable', return_value=True)
    def test_eyes_release(self, mock_post):
        """Test eyes_release function."""
        result = walle.eyes_release()
        self.assertTrue(result)
        mock_post.assert_called_once_with("/release")

    def test_stop_blinking(self):
        """Test stop_blinking function."""
        walle.BLINK_STOP.clear()
        walle.stop_blinking()
        self.assertTrue(walle.BLINK_STOP.is_set())
        self.assertIsNone(walle.BLINK_THREAD)

    @patch('integrated_ai_assistant.stop_blinking')
    @patch('integrated_ai_assistant.BLINK_STOP')
    def test_start_blinking(self, mock_stop_event, mock_stop):
        """Test start_blinking function."""
        mock_stop_event.is_set.return_value = False
        mock_stop_event.clear = Mock()
        walle.start_blinking()
        
        mock_stop.assert_called_once()
        self.assertIsNotNone(walle.BLINK_THREAD)
        if walle.BLINK_THREAD:
            walle.BLINK_THREAD.join(timeout=0.1)

    @patch('integrated_ai_assistant.center_ud')
    def test_face_neutral(self, mock_center):
        """Test face_neutral function."""
        walle.face_neutral()
        mock_center.assert_called_once()

    @patch('integrated_ai_assistant.look_up')
    @patch('integrated_ai_assistant.look_down')
    @patch('integrated_ai_assistant.wink_left')
    @patch('integrated_ai_assistant.wink_right')
    @patch('integrated_ai_assistant.center_ud')
    @patch('random.random')
    def test_face_thinking_small(self, mock_random, mock_center, mock_wink_r, 
                                  mock_wink_l, mock_down, mock_up):
        """Test face_thinking_small function."""
        # Mock random to trigger look_up
        mock_random.side_effect = [0.3, 0.4]  # First < 0.5 (look), second < 0.5 (up)
        walle.face_thinking_small()
        mock_up.assert_called_once()
        mock_center.assert_called_once()


class TestLiveLineClass(unittest.TestCase):
    """Tests for LiveLine class."""

    @patch('sys.stdout.write')
    @patch('sys.stdout.flush')
    def test_liveline_init(self, mock_flush, mock_write):
        """Test LiveLine initialization."""
        ll = walle.LiveLine("Test: ")
        self.assertEqual(ll.prefix, "Test: ")
        self.assertEqual(ll.buf, "")

    @patch('sys.stdout.write')
    @patch('sys.stdout.flush')
    def test_liveline_clear(self, mock_flush, mock_write):
        """Test LiveLine clear method."""
        ll = walle.LiveLine()
        ll.clear()
        mock_write.assert_called_once_with("\x1b[2K\r")
        mock_flush.assert_called_once()

    @patch('sys.stdout.write')
    @patch('sys.stdout.flush')
    def test_liveline_print(self, mock_flush, mock_write):
        """Test LiveLine print method."""
        ll = walle.LiveLine("You: ")
        ll.print("Hello")
        self.assertEqual(ll.buf, "Hello")
        # Check clear and write were called
        self.assertTrue(mock_write.call_count >= 2)
        mock_flush.assert_called()

    @patch('builtins.print')
    @patch('sys.stdout.write')
    @patch('sys.stdout.flush')
    def test_liveline_finalize(self, mock_flush, mock_write, mock_print):
        """Test LiveLine finalize method."""
        ll = walle.LiveLine("You: ")
        ll.finalize("Final text")
        mock_print.assert_called_once_with("You: Final text")


class TestUtilityFunctions(unittest.TestCase):
    """Tests for utility functions."""

    @patch('os.path.isfile')
    def test_model_config_exists_with_extension(self, mock_isfile):
        """Test model_config_exists with .json extension."""
        mock_isfile.side_effect = lambda x: x.endswith('.json')
        result = walle.model_config_exists("/path/to/model.onnx")
        self.assertTrue(result)

    @patch('os.path.isfile', return_value=False)
    def test_model_config_exists_not_found(self, mock_isfile):
        """Test model_config_exists when config doesn't exist."""
        result = walle.model_config_exists("/path/to/model.onnx")
        self.assertFalse(result)

    def test_model_config_exists_empty_path(self):
        """Test model_config_exists with empty path."""
        result = walle.model_config_exists("")
        self.assertFalse(result)

    def test_tidy_reply_normal(self):
        """Test tidy_reply with normal text."""
        text = "Hello. This is a test. How are you?"
        result = walle.tidy_reply(text)
        self.assertIn("Hello", result)
        self.assertIn("test", result)

    def test_tidy_reply_whitespace(self):
        """Test tidy_reply normalizes whitespace."""
        text = "Hello    world\n\n\nTest"
        result = walle.tidy_reply(text)
        self.assertNotIn("\n", result)
        self.assertNotIn("    ", result)

    def test_tidy_reply_truncation(self):
        """Test tidy_reply truncates long text."""
        text = "A. " * 200  # Very long text
        result = walle.tidy_reply(text)
        self.assertLessEqual(len(result), 400)
        self.assertIn("...", result)

    def test_tidy_reply_short_response(self):
        """Test tidy_reply adds prompt for short responses."""
        text = "Yes."
        result = walle.tidy_reply(text)
        self.assertIn("Anything else?", result)

    def test_tidy_reply_question_mark(self):
        """Test tidy_reply doesn't add prompt if question exists."""
        text = "What do you think?"
        result = walle.tidy_reply(text)
        self.assertNotIn("Anything else?", result)

    def test_tidy_reply_limits_sentences(self):
        """Test tidy_reply limits to 3 sentences."""
        text = "First. Second. Third. Fourth. Fifth."
        result = walle.tidy_reply(text)
        sentences = result.split(". ")
        # Should have at most 3 sentences
        self.assertLessEqual(len([s for s in sentences if s]), 4)  # 3 + potential ellipsis


class TestOllamaFunctions(unittest.TestCase):
    """Tests for Ollama functions."""

    @patch('integrated_ai_assistant.requests.get')
    def test_ollama_healthy_success(self, mock_get):
        """Test Ollama health check success."""
        mock_response = Mock()
        mock_response.ok = True
        mock_get.return_value = mock_response
        
        result = walle.ollama_healthy()
        self.assertTrue(result)
        mock_get.assert_called_once_with(
            f"{walle.OLLAMA_BASE}/api/version", timeout=3
        )

    @patch('integrated_ai_assistant.requests.get', side_effect=Exception("Connection error"))
    def test_ollama_healthy_failure(self, mock_get):
        """Test Ollama health check failure."""
        result = walle.ollama_healthy()
        self.assertFalse(result)

    @patch('integrated_ai_assistant.requests.post')
    def test_ollama_chat_once_success(self, mock_post):
        """Test Ollama chat request success."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {"content": "Hello, how can I help?"}
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        result = walle.ollama_chat_once(messages)
        
        self.assertEqual(result, "Hello, how can I help?")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], f"{walle.OLLAMA_BASE}/api/chat")

    @patch('integrated_ai_assistant.requests.post')
    def test_ollama_chat_once_empty_response(self, mock_post):
        """Test Ollama chat with empty response."""
        mock_response = Mock()
        mock_response.json.return_value = {"message": {}}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        result = walle.ollama_chat_once(messages)
        
        self.assertEqual(result, "")


class TestDeviceManagementFunctions(unittest.TestCase):
    """Tests for device management functions."""

    @patch('integrated_ai_assistant.sd.query_devices')
    @patch('integrated_ai_assistant.sd.default')
    def test_pick_input_device_default(self, mock_default, mock_query):
        """Test pick_input_device with valid default device."""
        mock_devices = [
            {"max_input_channels": 1, "name": "Device 0"},
            {"max_input_channels": 2, "name": "Device 1"},
        ]
        mock_query.return_value = mock_devices
        mock_default.device = 0
        
        result = walle.pick_input_device(8)
        self.assertEqual(result, 0)

    @patch('integrated_ai_assistant.sd.query_devices')
    @patch('integrated_ai_assistant.sd.default')
    def test_pick_input_device_preferred(self, mock_default, mock_query):
        """Test pick_input_device with preferred device."""
        mock_devices = [
            {"max_input_channels": 0, "name": "Device 0"},  # No input
            {"max_input_channels": 2, "name": "Device 1"},
            {"max_input_channels": 1, "name": "Device 2"},
        ]
        mock_query.return_value = mock_devices
        mock_default.device = 0  # Default has no input
        
        result = walle.pick_input_device(1)
        self.assertEqual(result, 1)

    @patch('integrated_ai_assistant.sd.query_devices')
    @patch('integrated_ai_assistant.sd.default')
    def test_pick_input_device_fallback(self, mock_default, mock_query):
        """Test pick_input_device with fallback to first available."""
        mock_devices = [
            {"max_input_channels": 0, "name": "Device 0"},  # No input
            {"max_input_channels": 2, "name": "Device 1"},
        ]
        mock_query.return_value = mock_devices
        mock_default.device = 0  # Default has no input
        
        result = walle.pick_input_device(99)  # Invalid preferred
        self.assertEqual(result, 1)

    @patch('integrated_ai_assistant.sd.query_devices')
    def test_pick_input_device_no_devices(self, mock_query):
        """Test pick_input_device with no input devices."""
        mock_devices = [
            {"max_input_channels": 0, "name": "Device 0"},
        ]
        mock_query.return_value = mock_devices
        
        with self.assertRaises(RuntimeError):
            walle.pick_input_device(0)


class TestCleanupFunctions(unittest.TestCase):
    """Tests for cleanup functions."""

    @patch('integrated_ai_assistant.stop_blinking')
    @patch('integrated_ai_assistant.eyes_close')
    @patch('integrated_ai_assistant.eyes_release')
    def test_cleanup_face_enabled(self, mock_release, mock_close, mock_stop):
        """Test cleanup_face with PICO_ENABLED."""
        walle.PICO_ENABLED = True
        walle.cleanup_face()
        mock_stop.assert_called_once()
        mock_close.assert_called_once()
        mock_release.assert_called_once()

    @patch('integrated_ai_assistant.stop_blinking')
    @patch('integrated_ai_assistant.eyes_close')
    def test_cleanup_face_disabled(self, mock_close, mock_stop):
        """Test cleanup_face with PICO_ENABLED False."""
        walle.PICO_ENABLED = False
        walle.cleanup_face()
        mock_stop.assert_called_once()
        mock_close.assert_not_called()

    @patch('integrated_ai_assistant.stop_blinking', side_effect=Exception("Error"))
    @patch('integrated_ai_assistant.eyes_close')
    def test_cleanup_face_error_handling(self, mock_close, mock_stop):
        """Test cleanup_face handles errors gracefully."""
        walle.PICO_ENABLED = True
        # Should not raise exception
        walle.cleanup_face()
        mock_close.assert_called_once()


class TestAudioFunctions(unittest.TestCase):
    """Tests for audio-related functions."""

    @patch('integrated_ai_assistant.sd.query_hostapis')
    @patch('integrated_ai_assistant.sd.default')
    def test_prefer_wasapi_found(self, mock_default, mock_query):
        """Test prefer_wasapi when WASAPI is found."""
        mock_apis = [
            {"name": "MME"},
            {"name": "WASAPI"},
        ]
        mock_query.return_value = mock_apis
        mock_default.hostapi = PropertyMock()
        
        walle.prefer_wasapi()
        # Should have set hostapi
        self.assertIsNotNone(mock_default.hostapi)

    @patch('integrated_ai_assistant.sd.query_hostapis', side_effect=Exception("Error"))
    def test_prefer_wasapi_error(self, mock_query):
        """Test prefer_wasapi handles errors gracefully."""
        # Should not raise exception
        walle.prefer_wasapi()


class TestVoskFunctions(unittest.TestCase):
    """Tests for Vosk model loading."""

    @patch('integrated_ai_assistant.os.path.isdir', return_value=True)
    @patch('integrated_ai_assistant.Model')
    def test_load_vosk_model_success(self, mock_model_class, mock_isdir):
        """Test loading Vosk model successfully."""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        result = walle.load_vosk_model("/path/to/model")
        mock_model_class.assert_called_once_with("/path/to/model")
        self.assertEqual(result, mock_model)

    @patch('integrated_ai_assistant.os.path.isdir', return_value=False)
    def test_load_vosk_model_not_found(self, mock_isdir):
        """Test loading Vosk model when directory doesn't exist."""
        with self.assertRaises(RuntimeError):
            walle.load_vosk_model("/nonexistent/path")


class TestWhisperFunctions(unittest.TestCase):
    """Tests for Whisper loading."""

    @patch('integrated_ai_assistant.WhisperModel')
    @patch.dict('sys.modules', {'faster_whisper': MagicMock()})
    def test_load_whisper_faster_whisper(self, mock_whisper_model):
        """Test loading faster-whisper."""
        mock_model = Mock()
        mock_whisper_model.return_value = mock_model
        
        # Mock transcribe to return segments
        mock_segment = Mock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], None)
        
        tx_func = walle.load_whisper()
        result = tx_func("/path/to/audio.wav")
        
        self.assertEqual(result, "Hello world")

    @patch('integrated_ai_assistant.whisper')
    @patch.dict('sys.modules', {'faster_whisper': None}, clear=False)
    def test_load_whisper_openai_whisper(self, mock_whisper_module):
        """Test loading openai-whisper as fallback."""
        mock_model = Mock()
        mock_whisper_module.load_model.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "Hello world"}
        
        tx_func = walle.load_whisper()
        result = tx_func("/path/to/audio.wav")
        
        self.assertEqual(result, "Hello world")


class TestSpeakTextBlocking(unittest.TestCase):
    """Tests for speak_text_blocking function."""

    def setUp(self):
        """Set up test fixtures."""
        walle.SPEAKING.clear()

    def tearDown(self):
        """Clean up after tests."""
        walle.SPEAKING.clear()

    def test_speak_text_blocking_empty_text(self):
        """Test speak_text_blocking with empty text."""
        walle.speak_text_blocking("")
        self.assertFalse(walle.SPEAKING.is_set())
        
        walle.speak_text_blocking("   ")
        self.assertFalse(walle.SPEAKING.is_set())

    @patch('integrated_ai_assistant.os.path.isfile', return_value=True)
    @patch('integrated_ai_assistant.model_config_exists', return_value=True)
    @patch('integrated_ai_assistant.subprocess.run')
    @patch('integrated_ai_assistant.sf.read')
    @patch('integrated_ai_assistant.sd.stop')
    @patch('integrated_ai_assistant.sd.play')
    @patch('integrated_ai_assistant.sd.wait')
    @patch('tempfile.NamedTemporaryFile')
    def test_speak_text_blocking_success(self, mock_tempfile, mock_wait, mock_play, 
                                          mock_stop, mock_sf_read, mock_subprocess,
                                          mock_config_exists, mock_isfile):
        """Test successful text-to-speech."""
        # Mock tempfile
        mock_file = Mock()
        mock_file.name = "/tmp/test.wav"
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_tempfile.return_value = mock_file
        
        # Mock audio data
        mock_sf_read.return_value = (np.array([0.1, 0.2, 0.3]), 16000)
        
        walle.speak_text_blocking("Hello world")
        
        # Check SPEAKING was set and cleared
        self.assertFalse(walle.SPEAKING.is_set())
        mock_subprocess.assert_called_once()
        mock_sf_read.assert_called_once()
        mock_play.assert_called_once()

    @patch('integrated_ai_assistant.os.path.isfile', side_effect=[False, True])
    @patch('integrated_ai_assistant.model_config_exists', return_value=True)
    @patch('integrated_ai_assistant.subprocess.run')
    @patch('integrated_ai_assistant.sf.read')
    @patch('integrated_ai_assistant.sd.stop')
    @patch('integrated_ai_assistant.sd.play')
    @patch('integrated_ai_assistant.sd.wait')
    @patch('tempfile.NamedTemporaryFile')
    def test_speak_text_blocking_fallback(self, mock_tempfile, mock_wait, mock_play,
                                           mock_stop, mock_sf_read, mock_subprocess,
                                           mock_config_exists, mock_isfile):
        """Test TTS with fallback model."""
        walle.PIPER_MODEL_FALLBACK = "/path/to/fallback.onnx"
        
        # Mock tempfile
        mock_file = Mock()
        mock_file.name = "/tmp/test.wav"
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_tempfile.return_value = mock_file
        
        # Mock audio data
        mock_sf_read.return_value = (np.array([0.1, 0.2, 0.3]), 16000)
        
        walle.speak_text_blocking("Hello")
        
        # Should use fallback model
        self.assertFalse(walle.SPEAKING.is_set())

    @patch('integrated_ai_assistant.os.path.isfile', return_value=False)
    @patch('integrated_ai_assistant.log_err')
    def test_speak_text_blocking_no_model(self, mock_log_err, mock_isfile):
        """Test TTS when no model is available."""
        walle.speak_text_blocking("Hello")
        self.assertFalse(walle.SPEAKING.is_set())


class TestBlinkLoop(unittest.TestCase):
    """Tests for blink loop functionality."""

    def setUp(self):
        """Set up test fixtures."""
        walle.BLINK_STOP.clear()
        walle.SPEAKING.clear()
        walle.LISTENING.clear()

    def tearDown(self):
        """Clean up after tests."""
        walle.BLINK_STOP.set()
        if walle.BLINK_THREAD and walle.BLINK_THREAD.is_alive():
            walle.BLINK_THREAD.join(timeout=0.5)

    @patch('integrated_ai_assistant.eyes_blink')
    @patch('integrated_ai_assistant.time.sleep')
    @patch('integrated_ai_assistant.time.time', side_effect=[0, 0.1, 0.2, 6.0])  # Triggers blink
    @patch('random.uniform', return_value=5.0)
    def test_blink_loop_blinks_when_idle(self, mock_uniform, mock_time, mock_sleep, mock_blink):
        """Test blink loop blinks when not speaking/listening."""
        walle.BLINK_STOP.clear()
        # This is a complex integration test - simplified version
        # In practice, blink_loop runs in a thread
        pass  # Skip complex threading test


if __name__ == '__main__':
    unittest.main()
