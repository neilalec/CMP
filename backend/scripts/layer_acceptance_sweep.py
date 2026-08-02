import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_core
from app_state import QUEUE_MODES


def classify_response(response):
    text = str(response or '').lower()
    if 'layer not found' in text or 'unable to change layer' in text:
        return 'REJECTED'
    return 'ACCEPTED'


def main():
    parser = argparse.ArgumentParser(description='Run RCON layer acceptance checks.')
    parser.add_argument('--server-id', type=int, default=1)
    parser.add_argument('--mode', action='append', required=True)
    parser.add_argument('--delay-seconds', type=float, default=1.0)
    parser.add_argument('--only-problems', action='store_true')
    parser.add_argument('--report-file')
    args = parser.parse_args()

    results = []
    for mode_id in args.mode:
        queue_mode = QUEUE_MODES[mode_id]
        for layer in queue_mode['map_pool']:
            started = time.time()
            response = ''
            error = ''
            try:
                result = app_core.change_server_to_selected_map(layer, server_id=args.server_id)
                response = str(result.get('response') or '')
                status = classify_response(response)
            except Exception as exc:
                status = 'ERROR'
                error = str(exc)

            item = {
                'mode': mode_id,
                'layer': layer,
                'status': status,
                'response': response,
                'error': error,
                'elapsed': round(time.time() - started, 2),
            }
            results.append(item)
            if not args.only_problems or status != 'ACCEPTED':
                print(
                    f"{status} {mode_id} {layer} "
                    f"response={response or '-'} error={error or '-'}",
                    flush=True,
                )
            time.sleep(args.delay_seconds)

    problem_results = [
        result for result in results if result['status'] in {'REJECTED', 'ERROR'}
    ]
    summary = {
        'checked': len(results),
        'accepted': len(results) - len(problem_results),
        'problems': len(problem_results),
        'problem_layers': problem_results,
    }
    if args.report_file:
        with open(args.report_file, 'w', encoding='utf-8') as report:
            json.dump({'summary': summary, 'results': results}, report, indent=2)

    print('SUMMARY', flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    if problem_results:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
