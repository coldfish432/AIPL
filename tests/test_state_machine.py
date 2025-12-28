from state import STATUS_DOING, STATUS_DONE, STATUS_TODO, is_valid_transition, touch_heartbeat, transition_task


# test状态transitions
def test_state_transitions():
    task = {"id": "t1", "status": STATUS_TODO}
    event = transition_task(task, STATUS_DOING, now=100.0, source="test")
    assert event["from"] == STATUS_TODO
    assert task["status"] == STATUS_DOING

    event = transition_task(task, STATUS_DONE, now=101.0, source="test")
    assert event["from"] == STATUS_DOING
    assert task["status"] == STATUS_DONE

    assert transition_task(task, STATUS_TODO, now=102.0) is None


# testisvalidtransitionmatrix
def test_is_valid_transition_matrix():
    assert is_valid_transition(STATUS_TODO, STATUS_DOING) is True
    assert is_valid_transition(STATUS_DOING, STATUS_DONE) is True
    assert is_valid_transition(STATUS_DONE, STATUS_TODO) is False


# testtouchheartbeatupdatestimestamp
def test_touch_heartbeat_updates_timestamp():
    task = {"id": "t1"}
    touch_heartbeat(task, now=123.0)
    assert task["heartbeat_ts"] == 123.0
