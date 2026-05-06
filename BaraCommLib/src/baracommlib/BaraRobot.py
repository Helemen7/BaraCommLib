from .config_manager import ConfigManager

class BaraRobot:
    def __init__(self, config_filepath: str = "baraconfig.yaml"):
        # Delegate config loading and validation to ConfigManager
        config_manager = ConfigManager(config_filepath)
        self.config = config_manager.load_and_validate()

        # Config is safe to use now
        self._setup_hw()
        
    def _setup_hw(self):
        # Initialize PWMs, initialize ToFs, initialize Gyro, initialize button, set them all to default state
        pass
        
    def setupSensors(self):
        pass