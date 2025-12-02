import sys

from wcpan.drive.cli.lib import get_media_info


media_info = get_media_info(sys.argv[1])
print(media_info)
