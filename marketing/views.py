"""Public, signed-out pages."""

from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.vary import vary_on_headers
from django.views.generic import TemplateView

from config.theme import is_valid_theme, set_theme_cookie

from . import content, releases


class MarketingPageMixin:
    """Context every page in the marketing shell needs: the nav and footer content."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            nav_links=content.NAV_LINKS,
            nav_sign_in=content.SIGN_IN,
            nav_account=content.ACCOUNT,
            nav_download=content.DOWNLOAD,
            footer_columns=content.FOOTER_COLUMNS,
            footer_tagline=content.FOOTER_TAGLINE,
            footer_signature=content.FOOTER_SIGNATURE,
        )
        return context


class HomeView(MarketingPageMixin, TemplateView):
    """The marketing Home at /."""

    template_name = "marketing/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            hero=content.HOME_HERO,
            features=content.HOME_FEATURES,
            workflow=content.HOME_WORKFLOW,
            facts=content.HOME_FACTS,
            toolbox=content.HOME_TOOLBOX,
            community=content.HOME_COMMUNITY,
            final=content.HOME_FINAL,
        )
        return context


class ToolboxView(MarketingPageMixin, TemplateView):
    """The Toolbox overview at /toolbox/: what it does, its screenshots, how to run it."""

    template_name = "marketing/toolbox.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["toolbox"] = content.TOOLBOX_PAGE
        return context


class CreditsView(MarketingPageMixin, TemplateView):
    """/credits/: the engine's NOTICE, every Rust crate and every Python package the
    engine and the Hub are built from (marketing/credits.py generates the lists)."""

    template_name = "marketing/credits.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["credits"] = content.CREDITS_PAGE
        return context


# A full-width download panel lays its builds out this many to a row (from 1024 px).
DOWNLOAD_COLUMNS = 3


@method_decorator(vary_on_headers("User-Agent", "Sec-CH-UA-Platform"), name="dispatch")
class DownloadView(MarketingPageMixin, TemplateView):
    """The engine's newest release at /download/, its builds grouped by system.

    The release comes from GitHub through marketing/releases.py's cache, which falls back
    to the last list GitHub gave and then to a plain link to GitHub Releases, so this page
    never fails because GitHub did. The visitor's system (from its headers) is highlighted.
    """

    template_name = "marketing/download.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offer = releases.current_release()
        system = releases.detect_system(
            self.request.headers.get("User-Agent", ""),
            self.request.headers.get("Sec-CH-UA-Platform", ""),
        )
        groups = (
            releases.group_builds(offer.release, content.DOWNLOAD_BUILDS, system)
            if offer.release
            else []
        )
        panels = [self._panel(group) for group in groups]
        mine = next((group for group in groups if group.detected and group.primary), None)
        context.update(
            page=content.DOWNLOAD_PAGE,
            offer=offer,
            # The systems' panels, then "other" (every other file).
            systems=[panel for panel in panels if panel["group"].system != "other"],
            others=next((panel for panel in panels if panel["group"].system == "other"), None),
            mine=mine,
            mine_name=content.DOWNLOAD_PAGE["systems"][mine.system] if mine else "",
            mine_icon=content.DOWNLOAD_SYSTEM_ICONS[mine.system] if mine else "",
        )
        return context

    @staticmethod
    def _panel(group: releases.SystemGroup) -> dict:
        """A system's panel: its name and icon, and whether it spans the row (several builds,
        laid out three to a row). A wide panel whose last row isn't full gets its tip card,
        spanning the gap (`tip_span` columns)."""
        wide = len(group.builds) > 1
        gap = (-len(group.builds)) % DOWNLOAD_COLUMNS if wide else 0
        tip = content.DOWNLOAD_PAGE["tips"].get(group.system) if gap else None
        return {
            "group": group,
            "name": content.DOWNLOAD_PAGE["systems"][group.system],
            "icon": content.DOWNLOAD_SYSTEM_ICONS[group.system],
            "wide": wide,
            "tip": tip,
            "tip_span": gap,
        }


class DownloadAgreeView(MarketingPageMixin, TemplateView):
    """The license agreement every download goes through, at /download/agree/?file=<name>.

    GET shows the terms and the form (the page JavaScript-less visitors reach; with
    JavaScript the same form opens as a dialog on /download/). POST, with CSRF, needs the
    agreement box ticked, then redirects (303) to that file's download on GitHub. The file
    is named, never linked: it must be in the current release, or it's a 404, so this can
    never redirect anywhere but the release's own files.
    """

    template_name = "marketing/download_agree.html"

    def _asset(self, name: object) -> releases.Asset:
        asset = releases.find_asset(releases.current_release().release, name)
        if asset is None:
            raise Http404("No such file in the current release.")
        return asset

    def get(self, request: HttpRequest) -> HttpResponse:
        asset = self._asset(request.GET.get("file"))
        return self.render_to_response(self.get_context_data(asset=asset))

    def post(self, request: HttpRequest) -> HttpResponse:
        asset = self._asset(request.POST.get("file"))
        if request.POST.get("agree") != "yes":
            context = self.get_context_data(asset=asset, missing_agreement=True)
            return self.render_to_response(context, status=400)
        return _see_other(asset.url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = content.DOWNLOAD_PAGE
        return context


def _see_other(url: str) -> HttpResponseRedirect:
    """A 303 to `url`: after the POST, the browser GETs the file."""
    response = HttpResponseRedirect(url)
    response.status_code = 303
    return response


class ThemeView(View):
    """Set the colour scheme without JavaScript: POST `choice`, with CSRF.

    Only "system", "light" or "dark" is accepted; anything else is a 400 and
    sets nothing. The visitor goes back to `next` when it's on this site,
    otherwise to Home. (With JavaScript, static/js/shell.js switches at once
    and writes the same cookie itself.)
    """

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        choice = request.POST.get("choice", "")
        if not is_valid_theme(choice):
            return HttpResponseBadRequest("Choose system, light or dark.")
        next_url = request.POST.get("next", "")
        safe = url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
        response = redirect(next_url if safe else "marketing:home")
        set_theme_cookie(response, choice)
        return response
