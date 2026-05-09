"""
State Machine for complex robot behaviors.
"""

from enum import Enum, auto
from typing import Callable, Optional, Dict, Any
import time

class StateMachineError(Exception):
    pass

class RobotState(Enum):
    """Base states - extend with your own."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()
    EMERGENCY_STOP = auto()

class State:
    """Base state class."""
    
    def __init__(self, name: str):
        self.name = name
        self._on_enter_actions = []
        self._on_exit_actions = []
        
    def on_enter(self, machine: 'StateMachine', previous: Optional['State'] = None):
        """Called when entering this state."""
        for action in self._on_enter_actions:
            action(machine, previous)
            
    def on_exit(self, machine: 'StateMachine', next_state: 'State'):
        """Called when leaving this state."""
        for action in self._on_exit_actions:
            action(machine, next_state)
            
    def update(self, machine: 'StateMachine') -> Optional['State']:
        """
        Update logic. Return new state to transition to, or None to stay.
        """
        return None
        
    def on_event(self, machine: 'StateMachine', event: str, data: Any = None):
        """Handle external events."""
        pass
        
    def add_on_enter(self, action: Callable):
        self._on_enter_actions.append(action)
        
    def add_on_exit(self, action: Callable):
        self._on_exit_actions.append(action)

class StateMachine:
    """
    Hierarchical state machine for robot behaviors.
    
    Usage:
        sm = StateMachine()
        sm.add_state(RobotState.IDLE, IdleState())
        sm.add_state(RobotState.RUNNING, RunningState())
        sm.start()
        
        while True:
            sm.update()
    """
    
    def __init__(self):
        self._states: Dict[RobotState, State] = {}
        self._current_state: Optional[State] = None
        self._current_state_enum: Optional[RobotState] = None
        self._is_running = False
        self._user_data = {}  # Shared data between states
        
    def add_state(self, state_enum: RobotState, state_obj: State):
        """Register a state."""
        self._states[state_enum] = state_obj
        
    def set_initial(self, state_enum: RobotState):
        """Set initial state."""
        if state_enum not in self._states:
            raise StateMachineError(f"State {state_enum} not registered")
        self._current_state_enum = state_enum
        self._current_state = self._states[state_enum]
        
    def start(self):
        """Start the state machine."""
        if not self._current_state:
            raise StateMachineError("No initial state set")
            
        self._is_running = True
        self._current_state.on_enter(self)
        
    def stop(self):
        """Stop the state machine."""
        self._is_running = False
        if self._current_state:
            self._current_state.on_exit(self, self._states.get(RobotState.IDLE, State("idle")))
            
    def update(self):
        """Update current state - call this in main loop."""
        if not self._is_running or not self._current_state:
            return
            
        new_state_enum = self._current_state.update(self)
        
        if new_state_enum:
            self.transition_to(new_state_enum)
            
    def transition_to(self, state_enum: RobotState):
        """Transition to a new state."""
        if state_enum not in self._states:
            raise StateMachineError(f"Unknown state: {state_enum}")
            
        old_state = self._current_state
        old_state.on_exit(self, self._states[state_enum])
        
        self._current_state_enum = state_enum
        self._current_state = self._states[state_enum]
        self._current_state.on_enter(self, old_state)
        
    def send_event(self, event: str, data: Any = None):
        """Send event to current state."""
        if self._current_state:
            self._current_state.on_event(self, event, data)
            
    @property
    def current_state(self) -> Optional[RobotState]:
        return self._current_state_enum
        
    @property
    def is_running(self) -> bool:
        return self._is_running
        
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get shared data."""
        return self._user_data.get(key, default)
        
    def set_data(self, key: str, value: Any):
        """Set shared data."""
        self._user_data[key] = value


# --- Example States ---

class IdleState(State):
    def __init__(self):
        super().__init__("Idle")
        
    def on_enter(self, machine: StateMachine, previous: Optional[State] = None):
        print("[Idle] Waiting...")
        
    def update(self, machine: StateMachine) -> Optional[RobotState]:
        # Check for start condition
        if machine.get_data("start_button_pressed"):
            return RobotState.RUNNING
        return None


class RunningState(State):
    def __init__(self):
        super().__init__("Running")
        self._last_update = time.time()
        
    def on_enter(self, machine: StateMachine, previous: Optional[State] = None):
        print("[Running] Robot active!")
        
    def update(self, machine: StateMachine) -> Optional[RobotState]:
        # Your main robot logic here
        # Return RobotState.ERROR on failure
        # Return RobotState.EMERGENCY_STOP on emergency
        return None
        
    def on_event(self, machine: StateMachine, event: str, data: Any = None):
        if event == "emergency":
            machine.transition_to(RobotState.EMERGENCY_STOP)