from ceilidh.input import describe_binding, parse_binding


def test_button_bindings_round_trip():
    assert parse_binding("button:7") == ("button", 7, None)
    assert describe_binding("button:7") == "Button 7"


def test_hat_bindings_carry_a_direction():
    assert parse_binding("hat:0:-1,0") == ("hat", 0, (-1, 0))
    assert describe_binding("hat:0:-1,0") == "D-pad Left"
    assert describe_binding("hat:0:0,1") == "D-pad Up"


def test_axis_bindings_carry_a_sign():
    assert parse_binding("axis:6:-") == ("axis", 6, -1)
    assert parse_binding("axis:6:+") == ("axis", 6, 1)
    assert describe_binding("axis:7:+") == "Axis 7+"


def test_rubbish_bindings_are_ignored_rather_than_crashing():
    assert parse_binding("button:banana") is None
    assert parse_binding("wobble:1") is None
    assert parse_binding("hat:0") is None
    assert describe_binding("wobble:1") == "wobble:1"
