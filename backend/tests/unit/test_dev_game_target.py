from runtime import should_resume_lobby_tasks, start_periodic_tasks


def test_wardogs_target_skips_squad_lobby_tasks_but_keeps_wardogs_and_shared_tasks():
    assert not should_resume_lobby_tasks('squad', 3, dev_mode=True, dev_game_target='wardogs')
    assert should_resume_lobby_tasks('squad', 5, dev_mode=True, dev_game_target='wardogs')
    assert should_resume_lobby_tasks('wardogs', 3, dev_mode=True, dev_game_target='wardogs')
    assert should_resume_lobby_tasks('squad', 3, dev_mode=True, dev_game_target='local')
    assert should_resume_lobby_tasks('squad', 3, dev_mode=False, dev_game_target='local')

    scheduled = []

    class SocketIO:
        def start_background_task(self, task):
            scheduled.append(task)

    shared = lambda: None
    wardogs_observer = lambda: None
    resumed_lobbies = []
    start_periodic_tasks(
        socketio=SocketIO(), periodic_queue_management=shared,
        cleanup_stale_players_task=shared, runtime_state_persistence_task=shared,
        resume_lobby_tasks=lambda: resumed_lobbies.append(True),
        wardogs_observation_task=wardogs_observer,
        logger=type('Logger', (), {'info': lambda *_: None, 'error': lambda *_: None})(),
    )
    assert len(scheduled) == 4
    assert scheduled[-1] is wardogs_observer
    assert resumed_lobbies == [True]


def test_squad_live_roll_is_suppressed_only_for_wardogs_dev(monkeypatch):
    import app as backend_app
    import app_core

    called = []
    monkeypatch.setattr(backend_app, 'DEV_MODE', True)
    monkeypatch.setattr(backend_app, 'DEV_GAME_TARGET', 'wardogs')
    monkeypatch.setattr(app_core, 'start_live_roll_monitor_service',
                        lambda **_kwargs: called.append('started'))
    assert app_core.start_live_roll_monitor('legacy-squad-lobby') is False
    assert called == []

    monkeypatch.setattr(backend_app, 'DEV_MODE', False)
    assert app_core.start_live_roll_monitor('legacy-squad-lobby') is None
    assert called == ['started']
