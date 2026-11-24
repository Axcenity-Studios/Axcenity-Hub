"""Public, signed-out pages."""

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
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
        names = content.DOWNLOAD_PAGE["systems"]
        mine = next((group for group in groups if group.detected and group.primary), None)
        context.update(
            page=content.DOWNLOAD_PAGE,
            offer=offer,
            # (group, its name): the systems' panels, then "other" (every other file).
            systems=[(group, names[group.system]) for group in groups if group.system != "other"],
            others=next((group for group in groups if group.system == "other"), None),
            mine=mine,
            mine_name=names[mine.system] if mine else "",
        )
        return context


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
