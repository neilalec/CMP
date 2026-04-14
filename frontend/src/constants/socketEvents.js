export const SOCKET_EVENTS = {
  // Connection events
  CONNECTION: {
    CONNECT: 'connect',
    DISCONNECT: 'disconnect',
    ERROR: 'connect_error',
    RECONNECT: 'reconnect'
  },

  // Authentication evesnts
  AUTH: {
    LOGIN: 'login',
    LOGIN_SUCCESS: 'login_success',
    LOGIN_ERROR: 'login_error',
    AUTHENTICATE: 'authenticate',
    AUTHENTICATION_SUCCESS: 'authentication_success',
    AUTHENTICATION_ERROR: 'authentication_error',
    REGISTER: 'register',
    REGISTER_SUCCESS: 'register_success',
    REGISTER_ERROR: 'register_error'
  },

  // Queue events
  QUEUE: {
    JOIN: 'join-queue',
    JOINED: 'queue_joined',
    LEAVE: 'leave-queue',
    LEFT: 'queue_left',
    UPDATE: 'queue_update',
    STATUS: 'queue_status',
    SEED: 'queue_seed',
    CLEAR: 'queue_clear',
    ACCEPT_MATCH: 'queue_accept_match',
    MATCH_ACCEPT_CANCELLED: 'queue_match_accept_cancelled',
  },

  // Lobby events
  LOBBY: {
    CREATED: 'lobby_created',
    JOIN: 'join-lobby',
    LEAVE: 'leave-lobby',
    UPDATE: 'lobby_update',
    DATA: 'lobby_data',
    GET_DATA: 'get-lobby-data',
    VOTE_MAP: 'vote-map',
    MAP_SELECTED: 'map_selected',
    START: 'start-lobby',
    READY: 'lobby_ready',
    SKIP_PHASE: 'skip-phase',
    PREV_PHASE: 'prev-phase',
    COUNTDOWN: {
      TEAMS: 'lobby_countdown_teams',
      VOTING: 'lobby_countdown_voting'
    },
    TEAMS_ASSIGNED: 'teams_assigned',
  },

  OPEN_LOBBIES: {
    STATUS: 'open_lobbies_status',
    UPDATE: 'open_lobbies_update'
  },

  COUNTDOWN: {
    TOGGLE_PAUSE: 'pause-countdown',
    PAUSE_STATE: 'countdown_pause_state',
    STATUS: 'countdown_status'
  },

  GROUP: {
    CREATE: 'group_create',
    JOIN: 'group_join',
    LEAVE: 'group_leave',
    STATUS: 'group_status',
    UPDATE: 'group_update',
    QUEUE: 'group_queue',
    UNQUEUE: 'group_unqueue'
  },

  MESSAGE: 'message',
}; 
