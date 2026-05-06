from baracommlib import BaraRobot

def test_robot_init():
    robot = BaraRobot()
    assert robot is not None
    assert isinstance(robot, BaraRobot)

test_robot_init()
