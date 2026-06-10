import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure pygame is initialized for event constants
import pygame
pygame.init()

# Import the controller module to be tested
from src.controller import DS4Input


class TestControllerMock(unittest.TestCase):
    def setUp(self):
        # Reset pygame controller modules
        if not hasattr(pygame, '_sdl2'):
            pygame._sdl2 = MagicMock()
        
    @patch('pygame.joystick.get_count')
    @patch('pygame.joystick.Joystick')
    @patch('pygame._sdl2.controller.is_controller')
    @patch('pygame._sdl2.controller.Controller')
    def test_sdl_controller_mode(self, mock_controller_cls, mock_is_controller, mock_joystick_cls, mock_get_count):
        """Test detection and input processing when a recognized SDL Controller is connected."""
        mock_get_count.return_value = 1
        mock_is_controller.return_value = True
        
        # Setup mock Joystick instance
        mock_joy = MagicMock()
        mock_joy.get_name.return_value = "Mock Controller"
        mock_joy.get_numbuttons.return_value = 14
        mock_joy.get_numaxes.return_value = 6
        mock_joy.get_numhats.return_value = 1
        mock_joy.rumble.return_value = True
        mock_joystick_cls.return_value = mock_joy
        
        # Setup mock Controller instance
        mock_ctrl = MagicMock()
        mock_ctrl.name = "Mock Controller"
        mock_ctrl.as_joystick.return_value = mock_joy
        mock_ctrl.rumble.return_value = True
        mock_controller_cls.return_value = mock_ctrl
        
        handler = DS4Input(joystick_index=0)
        success = handler.init()
        
        self.assertTrue(success)
        self.assertTrue(handler._is_sdl_controller)
        self.assertEqual(handler.name, "Mock Controller")
        self.assertTrue(handler.rumble_supported)
        
        # Test event processing for buttons
        # Press A (should map to 'X' and 'Cross' and 'A')
        ev_down = pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A)
        handler.process_event(ev_down)
        
        self.assertTrue(handler.held('X'))
        self.assertTrue(handler.held('Cross'))
        self.assertTrue(handler.held('A'))
        self.assertTrue(handler.just_pressed('X'))
        self.assertTrue(handler.just_pressed('Cross'))
        self.assertFalse(handler.just_released('X'))
        
        # Frame boundary update
        handler.update()
        self.assertTrue(handler.held('X'))
        self.assertFalse(handler.just_pressed('X'))
        
        # Release A
        ev_up = pygame.event.Event(pygame.CONTROLLERBUTTONUP, button=pygame.CONTROLLER_BUTTON_A)
        handler.process_event(ev_up)
        
        self.assertFalse(handler.held('X'))
        self.assertTrue(handler.just_released('X'))
        self.assertTrue(handler.just_released('Cross'))
        
        # Test stick inputs (Left Stick X/Y)
        ev_lx = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_LEFTX, value=26214) # ~0.8
        ev_ly = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_LEFTY, value=-19660) # ~-0.6
        handler.process_event(ev_lx)
        handler.process_event(ev_ly)
        
        # Stick left: values outside deadzone should be scaled
        lx, ly = handler.stick_left()
        self.assertNotEqual(lx, 0.0)
        self.assertNotEqual(ly, 0.0)
        
        # Inside deadzone
        ev_lx_zero = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_LEFTX, value=1638) # ~0.05
        ev_ly_zero = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_LEFTY, value=-1638) # ~-0.05
        handler.process_event(ev_lx_zero)
        handler.process_event(ev_ly_zero)
        lx, ly = handler.stick_left()
        self.assertEqual(lx, 0.0)
        self.assertEqual(ly, 0.0)
        
        # Test triggers
        ev_trig = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=26214) # ~0.8
        handler.process_event(ev_trig)
        # Normalization: SDL mode scales 0..32767 directly to 0.0..1.0
        self.assertAlmostEqual(handler.trigger_left(), 0.8, places=4)
        # Should synthesize L2 button press (since trigger > 0.5)
        self.assertTrue(handler.held('L2'))
        
        # Release trigger
        ev_trig_rel = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=0)
        handler.process_event(ev_trig_rel)
        self.assertAlmostEqual(handler.trigger_left(), 0.0)
        self.assertFalse(handler.held('L2'))
        
        # Rumble test
        handler.rumble(0.5, 0.5, 200)
        mock_ctrl.rumble.assert_called_with(0.5, 0.5, 200)

    @patch('pygame.joystick.get_count')
    @patch('pygame.joystick.Joystick')
    @patch('pygame._sdl2.controller.is_controller')
    def test_raw_joystick_xbox_profile(self, mock_is_controller, mock_joystick_cls, mock_get_count):
        """Test fallback to raw joystick mode with Xbox profile."""
        mock_get_count.return_value = 1
        mock_is_controller.return_value = False
        
        mock_joy = MagicMock()
        mock_joy.get_name.return_value = "Xbox One Controller"
        mock_joy.get_numbuttons.return_value = 11
        mock_joy.get_numaxes.return_value = 6
        mock_joy.get_numhats.return_value = 1
        mock_joy.rumble.return_value = True
        mock_joystick_cls.return_value = mock_joy
        
        handler = DS4Input(joystick_index=0)
        success = handler.init()
        
        self.assertTrue(success)
        self.assertFalse(handler._is_sdl_controller)
        self.assertEqual(handler.name, "Xbox One Controller")
        
        # Test event processing for raw button 0 (Xbox A -> mapped to 'X')
        ev_down = pygame.event.Event(pygame.JOYBUTTONDOWN, button=0)
        handler.process_event(ev_down)
        self.assertTrue(handler.held('X'))
        self.assertTrue(handler.just_pressed('X'))
        
        # Test raw axis motion: RX/RY should map to right stick (Xbox RX = axis 3, RY = axis 4)
        ev_rx = pygame.event.Event(pygame.JOYAXISMOTION, axis=3, value=0.7)
        ev_ry = pygame.event.Event(pygame.JOYAXISMOTION, axis=4, value=-0.7)
        handler.process_event(ev_rx)
        handler.process_event(ev_ry)
        
        rx, ry = handler.stick_right()
        self.assertNotEqual(rx, 0.0)
        self.assertNotEqual(ry, 0.0)
        
        # Test D-pad hat motion (synthesized buttons)
        ev_hat = pygame.event.Event(pygame.JOYHATMOTION, value=(0, 1)) # Up
        handler.process_event(ev_hat)
        self.assertTrue(handler.held('DPad Up'))
        self.assertTrue(handler.just_pressed('DPad Up'))
        
        # Rumble test
        handler.rumble(0.5, 0.5, 200)
        mock_joy.rumble.assert_called_with(0.5, 0.5, 200)


if __name__ == '__main__':
    unittest.main()
