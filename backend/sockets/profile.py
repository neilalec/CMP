def handle_profile_status_event(data, build_profile_status, get_user_profile, find_active_lobby_for_user, logger):
    try:
        username = data.get('username') if data else None
        return build_profile_status(username, get_user_profile, find_active_lobby_for_user)
    except Exception as e:
        logger.error(f"Error in handle_profile_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get profile'}


def handle_update_steam_id_event(
    data,
    update_steam_id,
    get_user_record,
    matchmaking_queue,
    is_user_in_any_lobby,
    save_users,
    users,
    get_user_profile,
    logger
):
    try:
        username = data.get('username') if data else None
        steam_id = data.get('steam_id') if data else None
        return update_steam_id(
            username,
            steam_id,
            get_user_record,
            matchmaking_queue,
            is_user_in_any_lobby,
            save_users,
            users,
            get_user_profile
        )
    except Exception as e:
        logger.error(f"Error in handle_update_steam_id: {str(e)}")
        return {'success': False, 'message': 'Failed to update Steam ID'}
