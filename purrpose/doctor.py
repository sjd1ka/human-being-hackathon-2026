"""Read-only local environment check: no network, memory writes or model calls."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).parent


def inspect_environment(reference=None, node='node'):
    python_ok = sys.version_info >= (3,12)
    assets = ['web/index.html','web/app.js','web/app.css','web/api-client.js','web/agent-map.js','web/dashboard.html','web/dashboard.js','web/dashboard.css','web/review-panel.js','fixtures/chat-samples.json',
              'web/research.html','web/research.js','fixtures/maple.json','hmem-bridge.mjs',
              'web/design-home.html','web/design-home.css','web/design-home.js',
              'web/design-favicon.svg','web/design-favicon-warm.svg',
              'web/organization-demo.html','web/organization-demo.js',
              'web/architecture.html','web/architecture.css']
    missing = [name for name in assets if not (ROOT/name).is_file()]
    try:
        ZoneInfo('America/Toronto')
        timezone_ok = True
    except ZoneInfoNotFoundError:
        timezone_ok = False
    node_major = None
    try:
        response = subprocess.run([node,'--version'],capture_output=True,text=True,timeout=5,check=True)
        node_major = int(response.stdout.strip().lstrip('v').split('.')[0])
    except (OSError,subprocess.SubprocessError,ValueError):
        pass
    memory_status = ('not_configured' if reference is None else
                     'reference_present_runtime_unverified' if Path(reference).is_file() else 'reference_missing')
    return {'python_version': '.'.join(map(str,sys.version_info[:3])),
            'python_requirement_met':python_ok,'missing_assets':missing,
            'offline_ready':python_ok and not missing,
            'ontario_timezone_available':timezone_ok,
            'real_source_analysis_environment_ready':python_ok and not missing and timezone_ok,
            'node_major':node_major,'node24_for_hmem':node_major is not None and node_major>=24,
            'hmem_reference':memory_status,
            'live_integration_verified_by_this_check':False,
            'nightshift':'deferred_not_checked', 'new_cloud_calls':0,'network_requests':0,
            'notes':['No keys, private files or local memories inspected.',
                     'Missing Node/reference blocks H-MEM, not the no-key fixture page.',
                     'Reference presence is not proof H-MEM works; run configured integration tests.',
                     'Missing Ontario timezone data prevents real-source date analysis; configure timezone data before that feature.',
                     'No dependencies installed or settings changed.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--node',default='node')
    args=parser.parse_args()
    result=inspect_environment(args.reference,args.node)
    print(json.dumps(result,indent=2))
    return 0 if result['offline_ready'] else 1


if __name__=='__main__':
    raise SystemExit(main())
