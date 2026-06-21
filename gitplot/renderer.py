"""Renderer: writes a Graphviz Digraph to a file and optionally opens a viewer."""

from __future__ import annotations

import importlib.resources
import logging
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import graphviz

log = logging.getLogger(__name__)


class Renderer:
    """Renders a graphviz.Digraph to a file and manages viewer launch."""

    def __init__(
        self,
        output_path: str = "gitplot.svg",
        output_format: str = "svg",
        viewer: str = "html",
    ) -> None:
        self.output_path = Path(output_path)
        self.output_format = output_format
        self.viewer = viewer
        self._html_written = False

    def render(self, dg: graphviz.Digraph) -> Path:
        """Render dg to output_path; return the path of the written file."""
        out_path = self.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if self.output_format == "mermaid":
            return self._render_mermaid(dg, out_path)

        # graphviz.render writes <filename>.<format> when given a source file.
        # We write the DOT to a temp file, render, then move to the desired path.
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as tmp:
            tmp_dot = Path(tmp.name)

        try:
            dg.save(filename=str(tmp_dot))
            rendered = Path(
                graphviz.render(
                    engine="dot",
                    format=self.output_format,
                    filepath=str(tmp_dot),
                    quiet=True,
                )
            )
            shutil.move(str(rendered), str(out_path))
        finally:
            tmp_dot.unlink(missing_ok=True)

        log.info("Rendered %s", out_path)
        return out_path

    def _render_mermaid(self, dg: graphviz.Digraph, out_path: Path) -> Path:
        from .mermaid import dot_to_mermaid

        mermaid_text = dot_to_mermaid(dg.source)
        out_path.write_text(mermaid_text, encoding="utf-8")
        log.info("Rendered %s", out_path)
        return out_path

    def open_viewer(self, out_path: Path) -> None:
        """Launch the configured viewer for out_path."""
        if self.viewer == "none":
            return

        if self.viewer == "html":
            self._open_html(out_path)
        else:
            self._open_auto(out_path)

    # ------------------------------------------------------------------
    # Viewer implementations
    # ------------------------------------------------------------------

    def _open_html(self, svg_path: Path) -> None:
        """Write display.html next to the SVG and open it once."""
        if self._html_written:
            return  # Already open; SVG polling handles subsequent updates

        html_path = svg_path.parent / "gitplot.html"
        _write_display_html(html_path, svg_path.name)
        self._open_auto(html_path)
        self._html_written = True

    def _open_auto(self, path: Path) -> None:
        """Best-effort: try xdg-open / open / start depending on platform."""
        system = platform.system()
        if system == "Darwin":
            cmd = ["open", str(path)]
        elif system == "Windows":
            cmd = ["start", "", str(path)]
        else:
            cmd = ["xdg-open", str(path)]

        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (FileNotFoundError, OSError) as exc:
            log.warning("Could not open viewer (%s): %s", cmd[0], exc)
            log.warning("Open manually: %s", path)


def _write_display_html(html_path: Path, svg_filename: str) -> None:
    """Write the auto-refreshing display HTML page."""
    # Try to load the bundled template; fall back to inline default.
    try:
        data = importlib.resources.files("gitplot").joinpath("display.html").read_text()
        html = data.replace("{{SVG_FILENAME}}", svg_filename)
    except Exception:
        html = _default_html(svg_filename)

    html_path.write_text(html, encoding="utf-8")
    log.info("Wrote viewer: %s", html_path)


def _default_html(svg_filename: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>GitPlot</title>
  <style>
    body {{ margin: 0; background: #1e1e1e; display: flex;
            flex-direction: column; height: 100vh; }}
    #status {{ background: #333; color: #aaa; padding: 4px 8px;
               font: 12px monospace; flex-shrink: 0; }}
    #container {{ flex: 1; overflow: auto; display: flex;
                  align-items: center; justify-content: center; padding: 8px; }}
    #container svg {{ max-width: 100%; max-height: 100%; }}
  </style>
</head>
<body>
  <div id="status">Connecting to gitplot...</div>
  <div id="container"></div>
  <script>
    const SVG = '{svg_filename}';
    let lastContent = '';
    async function refresh() {{
      try {{
        const r = await fetch(SVG + '?t=' + Date.now());
        const text = await r.text();
        if (text !== lastContent) {{
          lastContent = text;
          document.getElementById('container').innerHTML = text;
          document.getElementById('status').textContent =
            'Updated: ' + new Date().toLocaleTimeString();
        }}
      }} catch (e) {{
        document.getElementById('status').textContent = 'Error: ' + e.message;
      }}
      setTimeout(refresh, 1000);
    }}
    refresh();
  </script>
</body>
</html>"""
