from mc_gateway.idle_monitor import wake_and_monitor, state
from mc_gateway.config import config


def test_wake_sequence_fast_forward(mocker):
    mocker.patch("mc_gateway.idle_monitor.is_crafty_up", return_value=True)
    mocker.patch("mc_gateway.idle_monitor.backend_reachable", return_value=True)
    mocker.patch("mc_gateway.idle_monitor.start_mc_server")
    mocker.patch("mc_gateway.idle_monitor.stop_mc_server")
    mocker.patch("mc_gateway.idle_monitor.crafty_process_manager.stop_crafty")

    # 1 check for startup, 2 checks for idle loop to reach IDLE_LIMIT
    players_mock = mocker.patch("mc_gateway.idle_monitor.get_player_count", side_effect=[0, 0, 0])

    config.CHECK_INTERVAL_SECONDS = 1
    config.IDLE_LIMIT_SECONDS = 2
    config.CRAFTY_IDLE_SECONDS = 1

    sleeps = []
    def fake_sleep(seconds):
        sleeps.append(seconds)

    state.waking = False

    wake_and_monitor(sleep_func=fake_sleep)

    assert state.waking is False
    assert sum(sleeps) == 3
    assert players_mock.call_count == 3
