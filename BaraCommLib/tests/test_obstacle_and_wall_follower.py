# Path configured in tests/conftest.py
from baracommlib.obstacle_avoidance import ObstacleAvoider, WallFollower
import pytest

def test_obstacleavoider_moves_forward():
    actions={}
    def move_forward(s):actions['move']=s
    def turn_left(s):actions['left']=s
    def turn_right(s):actions['right']=s
    def coast():actions['coast']=True
    avoider=ObstacleAvoider(
        get_sensor_reading=lambda sid: 200,
        move_forward=move_forward,turn_left=turn_left,turn_right=turn_right,coast=coast,
        front_sensor_ids=['front'],left_sensor_ids=[],right_sensor_ids=[]
    )
    avoider.update()
    assert 'move' in actions

def test_obstacleavoider_emergency_stop():
    # Simulate very close sensor reading to trigger coast+turn.
    actions={}
    def move_forward(s):actions['forward']=s
    def turn_left(s):actions['left']=s
    def turn_right(s):actions['right']=s
    def coast():actions['coast']=True
    avoider=ObstacleAvoider(
        get_sensor_reading=lambda sid: 50, # less than very_close (80)
        move_forward=move_forward,
        turn_left=turn_left,
        turn_right=turn_right,
        coast=coast,
        front_sensor_ids=['front'],left_sensor_ids=[],right_sensor_ids=[]
    )
    avoider.update()
    # Should have called coast and one of the turns
    assert 'coast' in actions
    assert ('left' in actions) or ('right' in actions)
