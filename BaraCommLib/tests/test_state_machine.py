import pytest
from baracomllib.state_machine import StateMachine, IdleState, RunningState, RobotState

def test_state_transition():
    sm = StateMachine()
    idle = IdleState()
    running = RunningState()
    # Register states
    sm.add_state(RobotState.IDLE, idle)
    sm.add_state(RobotState.RUNNING, running)

    sm.set_initial(RobotState.IDLE)
    sm.start()

    assert sm.current_state == RobotState.IDLE

    # Trigger transition by setting shared data flag used in IdleState.update
    sm.set_data("start_button_pressed", True)
    sm.update()

    assert sm.current_state == RobotState.RUNNING