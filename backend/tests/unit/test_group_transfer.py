from sockets.group import handle_group_kick_event, handle_group_transfer_event


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class DummyLogger:
    def error(self, message):
        self.last_error = message


def build_transfer_context():
    groups = {
        'ABC123': {
            'code': 'ABC123',
            'leader': 'alice',
            'members': ['alice', 'bob', 'carol'],
        }
    }
    user_to_group = {
        'alice': 'ABC123',
        'bob': 'ABC123',
        'carol': 'ABC123',
    }
    broadcasts = []

    def get_user_group(username):
        return user_to_group.get(username)

    def get_group_payload(code):
        group = groups.get(code)
        if not group:
            return None
        return {
            'code': group['code'],
            'leader': group['leader'],
            'members': list(group['members']),
        }

    def broadcast_group_update(code, payload):
        broadcasts.append((code, payload))

    return {
        'logger': DummyLogger(),
        'group_lock': DummyLock(),
        'queue_lock': DummyLock(),
        'matchmaking_queue': {
            'skirmish': [],
            'hotdrop': [],
        },
        'is_user_in_any_lobby': lambda username: False,
        'get_user_group': get_user_group,
        'groups': groups,
        'user_to_group': user_to_group,
        'get_group_payload': get_group_payload,
        'broadcast_group_update': broadcast_group_update,
        'broadcasts': broadcasts,
    }


def test_group_leader_can_transfer_ownership_to_member():
    context = build_transfer_context()
    broadcasts = context.pop('broadcasts')
    context.pop('user_to_group')

    response = handle_group_transfer_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        **context
    )

    assert response['success'] is True
    assert response['group']['leader'] == 'bob'
    assert context['groups']['ABC123']['leader'] == 'bob'
    assert broadcasts == [('ABC123', response['group'])]


def test_group_transfer_requires_current_leader():
    context = build_transfer_context()
    context.pop('broadcasts')
    context.pop('user_to_group')

    response = handle_group_transfer_event(
        {'username': 'bob', 'targetUsername': 'carol'},
        **context
    )

    assert response == {
        'success': False,
        'message': 'Only the leader can transfer group ownership',
    }
    assert context['groups']['ABC123']['leader'] == 'alice'


def test_group_transfer_target_must_be_member():
    context = build_transfer_context()
    context.pop('broadcasts')
    context.pop('user_to_group')

    response = handle_group_transfer_event(
        {'username': 'alice', 'targetUsername': 'dave'},
        **context
    )

    assert response == {
        'success': False,
        'message': 'Target user is not in this group',
    }
    assert context['groups']['ABC123']['leader'] == 'alice'


def test_group_transfer_is_blocked_while_group_is_queued():
    context = build_transfer_context()
    context.pop('broadcasts')
    context.pop('user_to_group')
    context['matchmaking_queue']['skirmish'].append('alice')

    response = handle_group_transfer_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        **context
    )

    assert response == {
        'success': False,
        'message': 'Leave the queue before transferring group ownership',
    }
    assert context['groups']['ABC123']['leader'] == 'alice'


def test_group_transfer_is_blocked_while_group_member_is_in_lobby():
    context = build_transfer_context()
    context.pop('broadcasts')
    context.pop('user_to_group')
    context['is_user_in_any_lobby'] = lambda username: username == 'carol'

    response = handle_group_transfer_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        **context
    )

    assert response == {
        'success': False,
        'message': 'Leave the lobby before transferring group ownership',
    }
    assert context['groups']['ABC123']['leader'] == 'alice'


class DummySocket:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def test_group_leader_can_kick_member():
    context = build_transfer_context()
    broadcasts = context.pop('broadcasts')
    socket = DummySocket()
    left_rooms = []

    response = handle_group_kick_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        socketio=socket,
        socket_events={'GROUP': {'UPDATE': 'group_update'}},
        get_player_sids=lambda username: ['sid-bob'] if username == 'bob' else [],
        leave_room=lambda room, sid=None: left_rooms.append((room, sid)),
        **context
    )

    assert response['success'] is True
    assert response['group']['members'] == ['alice', 'carol']
    assert context['user_to_group'] == {'alice': 'ABC123', 'carol': 'ABC123'}
    assert broadcasts == [('ABC123', response['group'])]
    assert socket.emits == [('group_update', {'success': True, 'group': None}, 'sid-bob')]
    assert left_rooms == [('ABC123', 'sid-bob')]


def test_group_kick_is_blocked_while_group_is_queued():
    context = build_transfer_context()
    context.pop('broadcasts')
    context['matchmaking_queue']['skirmish'].append('alice')

    response = handle_group_kick_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        socketio=DummySocket(),
        socket_events={'GROUP': {'UPDATE': 'group_update'}},
        get_player_sids=lambda username: [],
        leave_room=lambda room, sid=None: None,
        **context
    )

    assert response == {
        'success': False,
        'message': 'Leave the queue before changing group members',
    }
    assert context['groups']['ABC123']['members'] == ['alice', 'bob', 'carol']


def test_group_kick_is_blocked_while_group_member_is_in_lobby():
    context = build_transfer_context()
    context.pop('broadcasts')
    context['is_user_in_any_lobby'] = lambda username: username == 'carol'

    response = handle_group_kick_event(
        {'username': 'alice', 'targetUsername': 'bob'},
        socketio=DummySocket(),
        socket_events={'GROUP': {'UPDATE': 'group_update'}},
        get_player_sids=lambda username: [],
        leave_room=lambda room, sid=None: None,
        **context
    )

    assert response == {
        'success': False,
        'message': 'Leave the lobby before changing group members',
    }
    assert context['groups']['ABC123']['members'] == ['alice', 'bob', 'carol']
