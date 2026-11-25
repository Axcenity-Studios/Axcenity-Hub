"""Members' uploads (MEDIA_ROOT) on a development server.

Served only while DEBUG is on, decided per request rather than when the URLconf loads, so the
route is always the same and a production server (DEBUG off) answers 404: there, the web
server serves MEDIA_ROOT at MEDIA_URL itself.
"""

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def development_media(request, path: str):
    if not settings.DEBUG:
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
