"""Utility helpers for visordash.

Currently contains CSS asset URL rewriting logic used by the package.
"""
import re

# Precompile the CSS url(...) pattern for reuse. This matches url(
# optional-whitespace optional-quote /path ... optional-quote optional-whitespace )
# and captures the optional quote and the path. The pattern avoids consuming
# trailing whitespace so callers may choose whether to preserve formatting.
_CSS_URL_PATTERN = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<path>/[^\s'\")]+)(?P=quote)\s*\)",
    re.IGNORECASE,
)


def rewrite_css_urls(raw: str, base_path: str) -> str:
    """Rewrite absolute url(...) paths in the provided CSS bundle.

    Parameters
    ----------
    raw: str
        CSS content to rewrite
    base_path: str
        Prefix to prepend to any absolute path that starts with '/'

    The function rewrites only paths starting with a single leading slash
    (e.g. /fonts/, /wasm/, /visordash/) by prepending ``base_path`` while
    preserving quoting. It intentionally skips protocol-relative URLs
    (//...), full URLs (http://, https://), and other scheme-like paths.
    """
    if not base_path:
        return raw

    def _rewrite(m: re.Match) -> str:
        quote = m.group('quote') or ''
        path = m.group('path')
        # Skip protocol-relative URLs (//...)
        if path.startswith('//'):
            return m.group(0)
        # Skip patterns like /http:... or /data:... which shouldn't be rewritten
        if re.match(r"^/[a-zA-Z]+:", path):
            return m.group(0)
        return f"url({quote}{base_path}{path}{quote})"

    return _CSS_URL_PATTERN.sub(_rewrite, raw)

