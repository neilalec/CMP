import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_core
from app_state import QUEUE_MODES


DEFAULT_QUEUE_MODES = ('balt26', 'ocbt15', 'ocbt5', 'ocbt1', 'sec26', 'sec36', 'sec46')


def layer_snapshot(server_id=None):
    health = app_core.get_bridge_health(server_id=server_id)
    details = health.get('details') or {}
    return {
        'ok': bool(health.get('ok')),
        'currentLayer': (
            details.get('currentLayer')
            or details.get('currentLayerRaw')
            or details.get('currentLayerId')
            or ''
        ),
        'currentLevel': details.get('currentLevel') or '',
        'nextLayer': (
            details.get('nextLayer')
            or details.get('nextLayerRaw')
            or details.get('nextLayerId')
            or ''
        ),
        'nextLevel': details.get('nextLevel') or '',
        'playtimeSeconds': details.get('playtimeSeconds'),
        'playerCount': details.get('playerCount'),
        'serverName': details.get('serverName') or '',
    }


def current_layer(server_id=None):
    return layer_snapshot(server_id).get('currentLayer') or ''


def wait_for_ready(server_id, timeout_seconds, poll_seconds, stable_polls):
    deadline = time.time() + timeout_seconds
    previous = ''
    stable_count = 0
    last_snapshot = {}
    while time.time() < deadline:
        last_snapshot = layer_snapshot(server_id)
        current = last_snapshot.get('currentLayer') or ''
        if current and current == previous:
            stable_count += 1
        else:
            stable_count = 1 if current else 0
            previous = current
        if stable_count >= stable_polls:
            return True, last_snapshot
        time.sleep(poll_seconds)
    return False, last_snapshot


def wait_for_layer(
    server_id,
    expected_layer,
    timeout_seconds,
    poll_seconds,
    end_match_if_next_after=None,
):
    deadline = time.time() + timeout_seconds
    last_snapshot = {}
    end_match_sent = False
    while time.time() < deadline:
        last_snapshot = layer_snapshot(server_id)
        if last_snapshot.get('currentLayer') == expected_layer:
            return True, last_snapshot, end_match_sent
        if (
            end_match_if_next_after is not None
            and not end_match_sent
            and last_snapshot.get('nextLayer') == expected_layer
            and time.time() >= deadline - timeout_seconds + end_match_if_next_after
        ):
            app_core.end_server_match(server_id=server_id)
            end_match_sent = True
        time.sleep(poll_seconds)
    return False, last_snapshot, end_match_sent


def iter_layers(queue_modes):
    seen = set()
    for mode_id in queue_modes:
        mode = QUEUE_MODES[mode_id]
        for layer in mode['map_pool']:
            if layer in seen:
                continue
            seen.add(layer)
            yield mode_id, layer


def main():
    parser = argparse.ArgumentParser(
        description='Validate queue layer IDs by rolling a configured Squad server to each layer.'
    )
    parser.add_argument('--server-id', type=int)
    parser.add_argument('--default-bridge', action='store_true')
    parser.add_argument('--queue-mode', action='append', choices=sorted(QUEUE_MODES.keys()))
    parser.add_argument('--layer', action='append')
    parser.add_argument('--timeout-seconds', type=int, default=90)
    parser.add_argument('--poll-seconds', type=int, default=5)
    parser.add_argument('--delay-seconds', type=int, default=3)
    parser.add_argument('--ready-timeout-seconds', type=int, default=120)
    parser.add_argument('--ready-stable-polls', type=int, default=2)
    parser.add_argument('--end-match-if-next-after', type=int)
    parser.add_argument('--report-file')
    args = parser.parse_args()

    queue_modes = tuple(args.queue_mode or (() if args.layer else DEFAULT_QUEUE_MODES))
    layers = [(mode_id, layer) for mode_id, layer in iter_layers(queue_modes)]
    layers.extend(('manual', layer.strip()) for layer in (args.layer or []) if layer.strip())
    server_id = None if args.default_bridge else args.server_id
    target = 'default bridge' if args.default_bridge else f'server_id={server_id}'
    if server_id is None and not args.default_bridge:
        raise SystemExit('--server-id is required unless --default-bridge is set')

    print(f'Validating {len(layers)} layers on {target}: {", ".join(queue_modes)}', flush=True)

    results = []
    for index, (mode_id, layer) in enumerate(layers, start=1):
        print(f'[{index}/{len(layers)}] CHANGE {mode_id} {layer}', flush=True)
        started_at = time.time()
        command_ok = False
        response = ''
        error = ''
        matched = False
        observed_snapshot = {}
        ready_snapshot = {}
        end_match_sent = False

        try:
            ready, ready_snapshot = wait_for_ready(
                server_id,
                args.ready_timeout_seconds,
                args.poll_seconds,
                args.ready_stable_polls,
            )
            if not ready:
                raise RuntimeError('Server did not report a stable current layer before validation.')

            change_response = app_core.change_server_to_selected_map(layer, server_id=server_id)
            command_ok = bool(change_response.get('ok'))
            response = str(change_response.get('response') or '')
            if 'layer not found' in response.lower():
                observed_snapshot = layer_snapshot(server_id)
            else:
                matched, observed_snapshot, end_match_sent = wait_for_layer(
                    server_id,
                    layer,
                    args.timeout_seconds,
                    args.poll_seconds,
                    end_match_if_next_after=args.end_match_if_next_after,
                )
        except Exception as exc:
            error = str(exc)
            try:
                observed_snapshot = layer_snapshot(server_id)
            except Exception:
                observed_snapshot = {}

        status = 'PASS' if command_ok and matched else 'FAIL'
        elapsed = int(time.time() - started_at)
        observed = observed_snapshot.get('currentLayer') or ''
        next_layer = observed_snapshot.get('nextLayer') or ''
        print(
            f'{status} {layer} current={observed or "-"} next={next_layer or "-"} '
            f'endMatchSent={str(end_match_sent).lower()} elapsed={elapsed}s '
            f'response={response or "-"} error={error or "-"}',
            flush=True,
        )
        results.append({
            'mode_id': mode_id,
            'layer': layer,
            'status': status,
            'ready': ready_snapshot,
            'observed': observed_snapshot,
            'end_match_sent': end_match_sent,
            'response': response,
            'error': error,
            'elapsed': elapsed,
        })
        time.sleep(args.delay_seconds)

    print('SUMMARY', flush=True)
    for result in results:
        print(
            f"{result['status']} {result['mode_id']} {result['layer']} "
            f"current={(result['observed'].get('currentLayer') if isinstance(result['observed'], dict) else '') or '-'} "
            f"next={(result['observed'].get('nextLayer') if isinstance(result['observed'], dict) else '') or '-'} "
            f"endMatchSent={str(result['end_match_sent']).lower()} "
            f"error={result['error'] or '-'}",
            flush=True,
        )

    if args.report_file:
        with open(args.report_file, 'w', encoding='utf-8') as handle:
            json.dump(results, handle, indent=2)

    failed = [result for result in results if result['status'] != 'PASS']
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
