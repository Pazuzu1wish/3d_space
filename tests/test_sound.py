# pyrefly: ignore [missing-import]
import os
import time
import pytest
import wave
import numpy as np

# Force dummy audio driver for headless test environment
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
from src.sound_handler import SoundHandler

@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()

@pytest.fixture
def sound_handler():
    return SoundHandler(sample_rate=44100, bit_depth=-16, channels=2, buffer_size=512)

def test_sound_handler_init(sound_handler):
    assert pygame.mixer.get_init() is not None
    # Pygame CE on dummy driver may return slightly different configurations,
    # but the mixer should be properly initialized.
    assert sound_handler.sample_rate == 44100
    assert sound_handler.channels == 2

def test_wav_validation_success(sound_handler):
    # Verify the generated laser.wav passes validation
    laser_path = "assets/sounds/laser.wav"
    if os.path.exists(laser_path):
        sound_handler.validate_wav_header(laser_path)

def test_wav_validation_mismatch(sound_handler, tmp_path):
    # Create an invalid WAV (e.g. 22050 Hz)
    bad_path = str(tmp_path / "bad_resample.wav")
    
    # 22050 Hz mono 16-bit
    data = np.zeros(4410, dtype=np.int16)
    with wave.open(bad_path, 'wb') as w:
        w.setnchannels(1) # Mono (mismatch, expected Stereo=2)
        w.setsampwidth(2) # 16-bit
        w.setframerate(22050) # Mismatch, expected 44100Hz
        w.writeframes(data.tobytes())
        
    with pytest.raises(ValueError) as excinfo:
        sound_handler.validate_wav_header(bad_path)
    
    assert "Channel mismatch" in str(excinfo.value) or "Sample rate mismatch" in str(excinfo.value)

def test_trigger_cooldowns(sound_handler):
    # We mock a pygame Sound object to avoid relying on actual loading for play tests
    class MockSound:
        def __init__(self):
            self.vol = 1.0
        def set_volume(self, vol):
            self.vol = vol
        def get_num_channels(self):
            return 0
        def play(self):
            pass

    # Insert mock sound directly into handler cache
    sound_handler.sounds["laser"] = MockSound()
    sound_handler.cooldowns["laser"] = 0.0
    
    # First trigger should succeed
    res1 = sound_handler.play_sfx("laser")
    assert res1 is True
    
    # Second consecutive trigger should fail due to cooldown (laser cd = 0.08s)
    res2 = sound_handler.play_sfx("laser")
    assert res2 is False
    
    # Wait out the cooldown
    time.sleep(0.09)
    res3 = sound_handler.play_sfx("laser")
    assert res3 is True

def test_voice_limiting(sound_handler):
    class MockSound:
        def __init__(self):
            self.channels = 0
        def set_volume(self, vol):
            pass
        def get_num_channels(self):
            return self.channels
        def play(self):
            pass

    mock_sound = MockSound()
    sound_handler.sounds["missile"] = mock_sound
    sound_handler.cooldowns["missile"] = 0.0
    
    # Limit for missile is 2. 
    # If 0 channels playing, should play
    mock_sound.channels = 0
    assert sound_handler.play_sfx("missile") is True
    
    # Reset cooldown
    sound_handler.cooldowns["missile"] = 0.0
    
    # If 2 channels playing, should not play (voice limited)
    mock_sound.channels = 2
    assert sound_handler.play_sfx("missile") is False
